"""Exception hierarchy for the Web Function client.

A single base exception carries ``code``/``message``/``details``, with four
named subtypes -- matching the same four errors used by every other client
in the reference-client suite (Ruby, JS, PHP, Go, Java, C#).
"""

from __future__ import annotations

import re
from typing import Any, Optional

_CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")


class WebFunctionError(Exception):
    """Base exception for all Web Function client errors.

    ``code`` defaults to a mechanically-derived string from the class name
    (e.g. ``BadRequestError`` -> ``WFN_BAD_REQUEST_ERROR``) when none is given
    explicitly, matching the Ruby reference gem's behavior.
    """

    def __init__(self, message: str, *, code: Optional[str] = None, details: Any = None):
        super().__init__(message)
        self.message = message
        self.code = code or self._default_code()
        self.details = details

    def _default_code(self) -> str:
        name = _CAMEL_RE.sub("_", type(self).__name__).upper()
        return f"WFN_{name}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.message!r}, code={self.code!r}, details={self.details!r})"


class BadRequestError(WebFunctionError):
    """Raised when the server returns a 400 response."""


class UnexpectedStatusCodeError(WebFunctionError):
    """Raised when the server returns a status code other than 200 or 400."""


class JsonParseError(WebFunctionError):
    """Raised when the response body is not valid JSON."""


class UnresolvedPromiseError(WebFunctionError):
    """Raised when a Promise's value is accessed before it has been resolved."""

    def __init__(self, message: str = "Promise is not yet resolved", *, code: Optional[str] = None, details: Any = None):
        super().__init__(message, code=code, details=details)
