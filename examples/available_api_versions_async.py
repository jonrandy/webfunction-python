#!/usr/bin/env python3
"""Async equivalent of available_api_versions.py.

    RESERVEPAY_BEARER_TOKEN=... python examples/available_api_versions_async.py
"""

import asyncio
import os
import sys

from webfunction import AsyncClient, WebFunctionError

PACKAGE_URL = "https://api.reservepay.com/merchants"


async def run() -> int:
    token = os.environ.get("RESERVEPAY_BEARER_TOKEN")
    if not token:
        print("RESERVEPAY_BEARER_TOKEN is not set.", file=sys.stderr)
        print(f"Usage: RESERVEPAY_BEARER_TOKEN=... python {sys.argv[0]}", file=sys.stderr)
        return 1

    client = await AsyncClient.from_package_endpoint(PACKAGE_URL, bearer_auth=token)
    try:
        versions = await client.available_api_versions()
        print(versions)
    except WebFunctionError as e:
        print(f"{type(e).__name__}: {e.message} (code={e.code}, details={e.details})", file=sys.stderr)
        return 1
    finally:
        await client.aclose()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
