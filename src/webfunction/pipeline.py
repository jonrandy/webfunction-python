"""Call pipelining: Path/Promise/Pipeline, ported from the Ruby reference gem's
pipeline.rb/promise.rb.

Unlike the Ruby gem -- where an unresolved ``Promise#[]`` returns a bare ``Path``
rather than another ``Promise`` (arguably a quirk of the reference implementation) --
Python's version always returns a new ``Promise`` wrapping the deeper path, so
chained indexing (``promise["a"]["b"]``) keeps working and stays consistent with
what the Go/Java/C# clients do with their equivalent ``.Field()``/``.get()`` methods.
"""

from __future__ import annotations

from typing import Any, Callable, List, Union

from .errors import UnresolvedPromiseError

_UNSET = object()


class Path:
    """A JSONPath expression (e.g. ``"$[0].id"``) built up via indexing."""

    __slots__ = ("_path",)

    def __init__(self, path: str):
        self._path = path

    def __getitem__(self, key: Union[str, int]) -> "Path":
        if isinstance(key, int):
            return Path(f"{self._path}[{key}]")
        return Path(f"{self._path}.{key}")

    def __str__(self) -> str:
        return self._path

    def __repr__(self) -> str:
        return f"Path({self._path!r})"

    def __eq__(self, other):
        return isinstance(other, Path) and other._path == self._path


class Promise:
    """A placeholder for a value that will be resolved once its pipeline executes.

    A literal argument string starting with ``"$"`` must be escaped as ``"\\$"``
    per the pipelining spec -- that escaping is the caller's responsibility when
    building step bodies, same as every other client in the suite.
    """

    def __init__(self, pipeline: "Pipeline", path: Union[str, Path]):
        self._pipeline = pipeline
        self._path = path if isinstance(path, Path) else Path(path)
        self._value: Any = _UNSET

    @property
    def resolved(self) -> bool:
        return self._value is not _UNSET

    def __getitem__(self, key: Union[str, int]) -> Any:
        if self.resolved:
            return self._value[key]
        return Promise(self._pipeline, self._path[key])

    def field(self, key: Union[str, int]) -> "Promise":
        """Explicit equivalent of ``promise[key]``, for readability or non-literal keys."""
        return self[key]

    def __str__(self) -> str:
        return str(self._value) if self.resolved else str(self._path)

    def __repr__(self) -> str:
        return f"Promise({self._value!r})" if self.resolved else f"Promise({self._path!r})"

    def to_json_value(self) -> Any:
        """Used by the request layer's JSON encoder to serialize an embedded, unresolved
        Promise as its JSONPath string, or a resolved Promise as its real value."""
        return self._value if self.resolved else str(self._path)

    @property
    def value(self) -> Any:
        if not self.resolved:
            raise UnresolvedPromiseError()
        return self._value

    def _set_value(self, value: Any) -> None:
        self._value = value

    def resolve(self) -> Any:
        """Resolves the promise, executing its pipeline first if necessary."""
        if self.resolved:
            return self._value
        self._pipeline.execute()
        return self.value


class _BasePipeline:
    def __init__(self, url: str):
        self._url = url
        self._steps: List[dict] = []
        self._promises: List[Promise] = []

    def add_step(self, step: dict) -> Promise:
        n = len(self._promises)
        promise = Promise(self, f"$[{n}]")
        self._steps.append(step)
        self._promises.append(promise)
        return promise

    def _reset(self) -> None:
        self._steps = []
        self._promises = []

    def _args_for(self, returns: str) -> dict:
        if returns == "all":
            return {"steps": self._steps, "returns": "$"}
        if returns == "last":
            return {"steps": self._steps, "returns": "$[-1:]"}
        return {"steps": self._steps, "returns": returns}


class Pipeline(_BasePipeline):
    """A sequence of steps executed together as a single request, via a synchronous
    execute function injected by the owning (sync) Client."""

    def __init__(self, url: str, execute_fn: Callable[[str, dict], Any]):
        super().__init__(url)
        self._execute_fn = execute_fn

    def execute(self, returns: str = "all") -> Any:
        args = self._args_for(returns)
        response = self._execute_fn(self._url, args)

        if returns == "all":
            for promise, value in zip(self._promises, response):
                promise._set_value(value)
        elif returns == "last" and self._promises:
            self._promises[-1]._set_value(response)

        self._reset()
        return response


class AsyncPipeline(_BasePipeline):
    """Async equivalent of :class:`Pipeline`, via an async execute function injected by
    the owning (async) AsyncClient."""

    def __init__(self, url: str, execute_fn: Callable[[str, dict], Any]):
        super().__init__(url)
        self._execute_fn = execute_fn

    async def execute(self, returns: str = "all") -> Any:
        args = self._args_for(returns)
        response = await self._execute_fn(self._url, args)

        if returns == "all":
            for promise, value in zip(self._promises, response):
                promise._set_value(value)
        elif returns == "last" and self._promises:
            self._promises[-1]._set_value(response)

        self._reset()
        return response
