#!/usr/bin/env python3
"""Fetches the merchants package from api.reservepay.com and calls its
"available-api-versions" endpoint.

Requires a bearer token in the RESERVEPAY_BEARER_TOKEN environment variable:

    RESERVEPAY_BEARER_TOKEN=... python examples/available_api_versions.py
"""

import os
import sys

from webfunction import Client, WebFunctionError

PACKAGE_URL = "https://api.reservepay.com/merchants"


def main() -> int:
    token = os.environ.get("RESERVEPAY_BEARER_TOKEN")
    if not token:
        print("RESERVEPAY_BEARER_TOKEN is not set.", file=sys.stderr)
        print(f"Usage: RESERVEPAY_BEARER_TOKEN=... python {sys.argv[0]}", file=sys.stderr)
        return 1

    client = Client.from_package_endpoint(PACKAGE_URL, bearer_auth=token)
    try:
        versions = client.available_api_versions()
        print(versions)
    except WebFunctionError as e:
        print(f"{type(e).__name__}: {e.message} (code={e.code}, details={e.details})", file=sys.stderr)
        return 1
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
