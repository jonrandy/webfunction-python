"""Pagination wrapper, ported from the Ruby reference gem's page.rb.

Deliberate, ecosystem-wide deviation from the Ruby gem: pagination is detected via
the endpoint's ``paginated`` flag, not by sniffing the response shape (the shape-sniffing
approach is also the root cause of a real zero-item-pagination bug hit later on the Ruby
*codegen* side -- see ``/areas/wfn-ruby-codegen.md``). Go/Java/C# all made this same
deviation deliberately; Python does too, for consistency across the suite.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator, List, Optional


class Page:
    """A page of results from a paginated (sync) endpoint. Iterable over its items."""

    def __init__(self, *, items: list, next_body: Optional[dict], previous_body: Optional[dict],
                 fetch: Callable[[dict], Any]):
        self.items = items
        self._next_body = next_body
        self._previous_body = previous_body
        self._fetch = fetch

    @property
    def has_next(self) -> bool:
        return self._next_body is not None

    @property
    def has_previous(self) -> bool:
        return self._previous_body is not None

    def next_page(self) -> Optional[Any]:
        """Fetches the next page by posting the opaque ``next`` body to the same endpoint."""
        if self._next_body is None:
            return None
        return self._fetch(self._next_body)

    def previous_page(self) -> Optional[Any]:
        """Fetches the previous page by posting the opaque ``previous`` body to the same endpoint."""
        if self._previous_body is None:
            return None
        return self._fetch(self._previous_body)

    def __iter__(self) -> Iterator[Any]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]

    def __repr__(self) -> str:
        return f"Page(items={self.items!r}, has_next={self.has_next}, has_previous={self.has_previous})"

    @staticmethod
    def is_paginated_shape(response: Any) -> bool:
        """Whether ``response`` matches the pagination contract's shape. Not used for the
        wrap decision itself (see module docstring) but exposed for callers who want to
        double-check a server's response against the spec."""
        return (
            isinstance(response, dict)
            and "page" in response and "next" in response and "previous" in response
            and isinstance(response["page"], list)
            and (response["next"] is None or isinstance(response["next"], dict))
            and (response["previous"] is None or isinstance(response["previous"], dict))
        )

    @classmethod
    def wrap(cls, response: Any, *, paginated: bool, fetch: Callable[[dict], Any]) -> Any:
        """Wraps ``response`` in a Page when the endpoint declares the ``paginated`` flag,
        else returns it unchanged. ``fetch`` is called with the opaque ``next``/``previous``
        body and should return an already re-wrapped Page (or bare value) in turn."""
        if not paginated or not isinstance(response, dict):
            return response
        return cls(
            items=response.get("page") or [],
            next_body=response.get("next"),
            previous_body=response.get("previous"),
            fetch=fetch,
        )


class AsyncPage:
    """Async equivalent of :class:`Page`. ``next_page()``/``previous_page()`` must be awaited."""

    def __init__(self, *, items: list, next_body: Optional[dict], previous_body: Optional[dict],
                 fetch: Callable[[dict], Any]):
        self.items = items
        self._next_body = next_body
        self._previous_body = previous_body
        self._fetch = fetch

    @property
    def has_next(self) -> bool:
        return self._next_body is not None

    @property
    def has_previous(self) -> bool:
        return self._previous_body is not None

    async def next_page(self) -> Optional[Any]:
        if self._next_body is None:
            return None
        return await self._fetch(self._next_body)

    async def previous_page(self) -> Optional[Any]:
        if self._previous_body is None:
            return None
        return await self._fetch(self._previous_body)

    def __iter__(self) -> Iterator[Any]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]

    def __repr__(self) -> str:
        return f"AsyncPage(items={self.items!r}, has_next={self.has_next}, has_previous={self.has_previous})"

    @classmethod
    def wrap(cls, response: Any, *, paginated: bool, fetch: Callable[[dict], Any]) -> Any:
        if not paginated or not isinstance(response, dict):
            return response
        return cls(
            items=response.get("page") or [],
            next_body=response.get("next"),
            previous_body=response.get("previous"),
            fetch=fetch,
        )
