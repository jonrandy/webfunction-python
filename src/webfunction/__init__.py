"""webfunction -- a reference client library for the Web Function (wfn) protocol.

See https://webfunction.org for the protocol specification.
"""

from ._version import VERSION
from .client import AsyncClient, Client
from .errors import (
    BadRequestError,
    JsonParseError,
    UnexpectedStatusCodeError,
    UnresolvedPromiseError,
    WebFunctionError,
)
from .models import Argument, Attribute, DocumentedError, Endpoint, ObjectSchema, Package
from .page import AsyncPage, Page
from .pipeline import AsyncPipeline, Path, Pipeline, Promise
from . import wftype

__version__ = VERSION

__all__ = [
    "Client",
    "AsyncClient",
    "Package",
    "Endpoint",
    "Argument",
    "Attribute",
    "DocumentedError",
    "ObjectSchema",
    "Page",
    "AsyncPage",
    "Path",
    "Promise",
    "Pipeline",
    "AsyncPipeline",
    "WebFunctionError",
    "BadRequestError",
    "UnexpectedStatusCodeError",
    "JsonParseError",
    "UnresolvedPromiseError",
    "wftype",
    "VERSION",
]
