"""Client and AsyncClient, ported from the Ruby reference gem's client.rb.

Dynamic dispatch (``client.list_items(a="b")`` working without any generated code) is
implemented via ``__getattr__``, the same trick Ruby/JS/PHP use via method_missing /
Proxy / __call -- confirmed as the right default for Python too, matching the majority
of the reference-client suite.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx

from . import _request
from .models import Package
from .page import AsyncPage, Page
from .pipeline import AsyncPipeline, Pipeline


def _join_url(base_url: str, endpoint_name: str) -> str:
    # Plain RFC 3986 relative-reference resolution, matching Ruby's URI.join exactly
    # (webfunction-go originally used url.JoinPath here and had to switch to
    # url.URL.ResolveReference to match Ruby's semantics -- urljoin already does the
    # right thing, so no workaround is needed in Python).
    return urljoin(base_url, endpoint_name)


class Client:
    """A synchronous wrapper around a Web Function Package that provides a convenient
    interface for invoking endpoints.

    Example::

        client = Client.from_package_endpoint("https://api.example.com/package")
        client.list_items(a="b")  # => {"c": "d"}
    """

    def __init__(self, *, base_url: str, endpoints: Optional[List[str]] = None,
                 package: Optional[Package] = None, bearer_auth: Optional[str] = None,
                 version: Optional[str] = None, pipeline: Optional[Pipeline] = None,
                 http_client: Optional[httpx.Client] = None):
        self._package = package
        self._base_url = base_url
        self._endpoints: Dict[str, str] = {e.replace("-", "_"): e for e in (endpoints or [])}
        self.bearer_auth = bearer_auth
        self.version = version
        self.pipeline = pipeline
        self._http = http_client if http_client is not None else httpx.Client()
        self._owns_http = http_client is None

    # -- construction -----------------------------------------------------------------

    @classmethod
    def from_package_endpoint(cls, url: str, *, bearer_auth: Optional[str] = None,
                               version: Optional[str] = None, pipelined: bool = False,
                               http_client: Optional[httpx.Client] = None) -> "Client":
        http = http_client if http_client is not None else httpx.Client()
        response = _request.execute_sync(http, url, bearer_auth=bearer_auth, version=version, args={})
        package = Package.from_dict(response)
        return cls.from_package(package, bearer_auth=bearer_auth, version=version,
                                 pipelined=pipelined, http_client=http)

    @classmethod
    def from_url(cls, url: str, *, bearer_auth: Optional[str] = None, version: Optional[str] = None,
                 pipelined: bool = False, http_client: Optional[httpx.Client] = None) -> "Client":
        http = http_client if http_client is not None else httpx.Client()
        body = _request.get_body_sync(http, url, extra_query_params={"api_version": version})
        package = Package.from_dict(json.loads(body))
        return cls.from_package(package, bearer_auth=bearer_auth, version=version,
                                 pipelined=pipelined, http_client=http)

    @classmethod
    def from_package(cls, package: Package, *, bearer_auth: Optional[str] = None,
                      version: Optional[str] = None, pipelined: bool = False,
                      http_client: Optional[httpx.Client] = None) -> "Client":
        http = http_client if http_client is not None else httpx.Client()
        pipeline = None
        if pipelined and package.pipeline_url:
            pipeline = Pipeline(
                package.pipeline_url,
                lambda url, args: _request.execute_sync(http, url, bearer_auth=bearer_auth, version=version, args=args),
            )

        client = cls(
            package=package,
            base_url=package.base_url,
            endpoints=[e.name for e in package.endpoints],
            bearer_auth=bearer_auth,
            version=version,
            pipeline=pipeline,
            http_client=http,
        )

        for endpoint in package.endpoints:
            endpoint.client = client

        return client

    # -- invocation ---------------------------------------------------------------------

    def call(self, endpoint_name: str, args: Optional[dict] = None) -> Any:
        """Calls an endpoint by name with the given arguments. Paginated responses are
        wrapped in a :class:`Page`. When the client is pipelined, returns a
        :class:`~webfunction.pipeline.Promise` instead of executing immediately."""
        args = args or {}
        url = _join_url(self._base_url, endpoint_name)

        if self.pipeline is not None:
            step = {"url": url, "headers": _request.build_headers(self.bearer_auth, self.version), "body": args}
            return self.pipeline.add_step(step)

        return self._execute_and_wrap(url, args, endpoint_name)

    def _execute_and_wrap(self, url: str, args: dict, endpoint_name: str) -> Any:
        response = _request.execute_sync(self._http, url, bearer_auth=self.bearer_auth, version=self.version, args=args)
        endpoint = self._package.endpoint(endpoint_name) if self._package else None
        paginated = bool(endpoint and endpoint.paginated)
        return Page.wrap(response, paginated=paginated, fetch=lambda body: self._execute_and_wrap(url, body, endpoint_name))

    @property
    def package(self) -> Optional[Package]:
        return self._package

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- dynamic dispatch -----------------------------------------------------------------

    def __getattr__(self, name: str):
        # Only reached when normal attribute lookup fails.
        endpoints = self.__dict__.get("_endpoints", {})
        endpoint_name = endpoints.get(name)
        if endpoint_name is None:
            raise AttributeError(f"{type(self).__name__!r} object has no attribute or endpoint {name!r}")

        def _invoke(**kwargs):
            return self.call(endpoint_name, kwargs)

        return _invoke

    def __dir__(self):
        return list(super().__dir__()) + list(self.__dict__.get("_endpoints", {}).keys())

    def __repr__(self) -> str:
        return f"Client(base_url={self._base_url!r})"


class AsyncClient:
    """Async equivalent of :class:`Client`. All I/O methods (including dynamic-dispatch
    endpoint calls) return awaitables.

    Example::

        client = await AsyncClient.from_package_endpoint("https://api.example.com/package")
        await client.list_items(a="b")  # => {"c": "d"}
    """

    def __init__(self, *, base_url: str, endpoints: Optional[List[str]] = None,
                 package: Optional[Package] = None, bearer_auth: Optional[str] = None,
                 version: Optional[str] = None, pipeline: Optional[AsyncPipeline] = None,
                 http_client: Optional[httpx.AsyncClient] = None):
        self._package = package
        self._base_url = base_url
        self._endpoints: Dict[str, str] = {e.replace("-", "_"): e for e in (endpoints or [])}
        self.bearer_auth = bearer_auth
        self.version = version
        self.pipeline = pipeline
        self._http = http_client if http_client is not None else httpx.AsyncClient()
        self._owns_http = http_client is None

    # -- construction -----------------------------------------------------------------

    @classmethod
    async def from_package_endpoint(cls, url: str, *, bearer_auth: Optional[str] = None,
                                     version: Optional[str] = None, pipelined: bool = False,
                                     http_client: Optional[httpx.AsyncClient] = None) -> "AsyncClient":
        http = http_client if http_client is not None else httpx.AsyncClient()
        response = await _request.execute_async(http, url, bearer_auth=bearer_auth, version=version, args={})
        package = Package.from_dict(response)
        return await cls.from_package(package, bearer_auth=bearer_auth, version=version,
                                       pipelined=pipelined, http_client=http)

    @classmethod
    async def from_url(cls, url: str, *, bearer_auth: Optional[str] = None, version: Optional[str] = None,
                        pipelined: bool = False, http_client: Optional[httpx.AsyncClient] = None) -> "AsyncClient":
        http = http_client if http_client is not None else httpx.AsyncClient()
        body = await _request.get_body_async(http, url, extra_query_params={"api_version": version})
        package = Package.from_dict(json.loads(body))
        return await cls.from_package(package, bearer_auth=bearer_auth, version=version,
                                       pipelined=pipelined, http_client=http)

    @classmethod
    async def from_package(cls, package: Package, *, bearer_auth: Optional[str] = None,
                            version: Optional[str] = None, pipelined: bool = False,
                            http_client: Optional[httpx.AsyncClient] = None) -> "AsyncClient":
        http = http_client if http_client is not None else httpx.AsyncClient()
        pipeline = None
        if pipelined and package.pipeline_url:
            async def _exec(url, args):
                return await _request.execute_async(http, url, bearer_auth=bearer_auth, version=version, args=args)
            pipeline = AsyncPipeline(package.pipeline_url, _exec)

        client = cls(
            package=package,
            base_url=package.base_url,
            endpoints=[e.name for e in package.endpoints],
            bearer_auth=bearer_auth,
            version=version,
            pipeline=pipeline,
            http_client=http,
        )

        for endpoint in package.endpoints:
            endpoint.client = client

        return client

    # -- invocation ---------------------------------------------------------------------

    async def call(self, endpoint_name: str, args: Optional[dict] = None) -> Any:
        args = args or {}
        url = _join_url(self._base_url, endpoint_name)

        if self.pipeline is not None:
            step = {"url": url, "headers": _request.build_headers(self.bearer_auth, self.version), "body": args}
            return self.pipeline.add_step(step)

        return await self._execute_and_wrap(url, args, endpoint_name)

    async def _execute_and_wrap(self, url: str, args: dict, endpoint_name: str) -> Any:
        response = await _request.execute_async(self._http, url, bearer_auth=self.bearer_auth, version=self.version, args=args)
        endpoint = self._package.endpoint(endpoint_name) if self._package else None
        paginated = bool(endpoint and endpoint.paginated)

        async def _fetch(body):
            return await self._execute_and_wrap(url, body, endpoint_name)

        return AsyncPage.wrap(response, paginated=paginated, fetch=_fetch)

    @property
    def package(self) -> Optional[Package]:
        return self._package

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    # -- dynamic dispatch -----------------------------------------------------------------

    def __getattr__(self, name: str):
        endpoints = self.__dict__.get("_endpoints", {})
        endpoint_name = endpoints.get(name)
        if endpoint_name is None:
            raise AttributeError(f"{type(self).__name__!r} object has no attribute or endpoint {name!r}")

        async def _invoke(**kwargs):
            return await self.call(endpoint_name, kwargs)

        return _invoke

    def __dir__(self):
        return list(super().__dir__()) + list(self.__dict__.get("_endpoints", {}).keys())

    def __repr__(self) -> str:
        return f"AsyncClient(base_url={self._base_url!r})"
