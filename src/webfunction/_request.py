"""Low-level HTTP request/response handling shared by Client and AsyncClient, ported
from the Ruby reference gem's request.rb.

Gzip note: the wfn protocol always sends ``Accept-Encoding: gzip`` explicitly. This has
bitten *every* prior client in the suite -- webfunction-go and webfunction-java both
independently broke on gzip response bodies because their HTTP libraries disable their
own automatic decompression once the caller sets ``Accept-Encoding`` itself.
httpx does NOT have this problem: it decides whether to decompress based on the
response's ``Content-Encoding`` header, regardless of who set ``Accept-Encoding`` on the
request (verified directly against a mock gzip-compressing server -- see
tests/test_client.py::test_gzip_response). So no manual gzip handling is needed here,
but it's still covered by a real test rather than just assumed.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import httpx

from ._version import VERSION
from .errors import BadRequestError, JsonParseError, UnexpectedStatusCodeError
from .pipeline import Promise


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Promise):
        return obj.to_json_value()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def dumps(obj: Any) -> bytes:
    return json.dumps(obj, default=_json_default).encode("utf-8")


def build_headers(bearer_auth: Optional[str] = None, version: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"webfunction/{VERSION}",
        "Accept-Encoding": "gzip",
    }
    if bearer_auth:
        headers["Authorization"] = f"Bearer {bearer_auth}"
    if version:
        headers["Api-Version"] = version
    return headers


def parse_response(status: int, body: bytes) -> Any:
    """Parses a raw HTTP response per the wfn protocol, raising typed errors as needed.
    Does not do pagination wrapping -- that needs the endpoint's ``paginated`` flag, which
    only the caller (Client/AsyncClient) knows about."""
    if status not in (200, 400):
        raise UnexpectedStatusCodeError(
            f"Unexpected status code ({status})",
            details={"status_code": status, "raw_body": body.decode("utf-8", "replace")},
        )

    try:
        result = json.loads(body)
    except json.JSONDecodeError as e:
        raise JsonParseError(
            str(e),
            details={"status_code": status, "raw_body": body.decode("utf-8", "replace"), "original_exception": e},
        ) from e

    if status == 400:
        code, message, details = "WFN_BAD_REQUEST_ERROR", "Bad request", {"body": result}
        if (
            isinstance(result, list) and len(result) == 3
            and isinstance(result[0], str) and isinstance(result[1], str)
        ):
            code, message, details = result
        raise BadRequestError(message, code=code, details=details)

    return result


def execute_sync(http: httpx.Client, url: str, *, bearer_auth: Optional[str] = None,
                  version: Optional[str] = None, args: Any = None) -> Any:
    headers = build_headers(bearer_auth, version)
    response = http.post(url, headers=headers, content=dumps(args if args is not None else {}))
    return parse_response(response.status_code, response.content)


async def execute_async(http: httpx.AsyncClient, url: str, *, bearer_auth: Optional[str] = None,
                         version: Optional[str] = None, args: Any = None) -> Any:
    headers = build_headers(bearer_auth, version)
    response = await http.post(url, headers=headers, content=dumps(args if args is not None else {}))
    return parse_response(response.status_code, response.content)


def get_body_sync(http: httpx.Client, url: str, *, extra_query_params: Optional[dict] = None) -> bytes:
    params = {k: v for k, v in (extra_query_params or {}).items() if v is not None}
    headers = {"User-Agent": f"webfunction/{VERSION}", "Accept-Encoding": "gzip"}
    response = http.get(url, headers=headers, params=params)
    return response.content


async def get_body_async(http: httpx.AsyncClient, url: str, *, extra_query_params: Optional[dict] = None) -> bytes:
    params = {k: v for k, v in (extra_query_params or {}).items() if v is not None}
    headers = {"User-Agent": f"webfunction/{VERSION}", "Accept-Encoding": "gzip"}
    response = await http.get(url, headers=headers, params=params)
    return response.content
