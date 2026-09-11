"""Functional tests for webfunction.Client / AsyncClient.

Uses a hand-rolled mock HTTP server (stdlib http.server), the Python equivalent of
Go's httptest, Java's com.sun.net.httpserver, and C#'s HttpListener -- every one of
those was used as the real verification harness for its respective client, not just
"does it compile/import". This suite exercises a real functional round trip, not just
import-time checks.
"""

from __future__ import annotations

import asyncio
import gzip as gzip_module
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import webfunction as wf
from webfunction import wftype


class Router:
    """Maps (method, path) -> a handler(body: dict) -> (status, response_obj)."""

    def __init__(self):
        self.routes = {}

    def add(self, method: str, path: str, handler):
        self.routes[(method, path)] = handler

    def dispatch(self, method: str, path: str, query: str, body_bytes: bytes):
        handler = self.routes.get((method, path))
        if handler is None:
            return 404, {"error": "not found"}
        body = json.loads(body_bytes) if body_bytes else {}
        return handler(body, query)


def _make_handler(router: Router):
    class Handler(BaseHTTPRequestHandler):
        def _handle(self, method):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b""
            path, _, query = self.path.partition("?")
            status, response_obj = router.dispatch(method, path, query, raw)

            payload = json.dumps(response_obj).encode("utf-8")
            gzip_wanted = "gzip" in (self.headers.get("Accept-Encoding") or "")
            if gzip_wanted:
                payload = gzip_module.compress(payload)

            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if gzip_wanted:
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            self._handle("POST")

        def do_GET(self):
            self._handle("GET")

        def log_message(self, *args):
            pass

    return Handler


def start_server(router: Router):
    server = HTTPServer(("127.0.0.1", 0), _make_handler(router))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    return server, f"http://127.0.0.1:{port}"


PACKAGE = {
    "base_url": None,  # filled in per-test once the server port is known
    "pipeline_url": None,
    "name": "test-package",
    "endpoints": [
        {
            "name": "list-items",
            "returns": "object",
            "arguments": [
                {"name": "email", "type": "string.email", "flags": ["required"]},
            ],
        },
        {
            "name": "list-people",
            "returns": "object",
            "flags": ["paginated"],
        },
        {
            "name": "get-widget",
            "returns": "object.widget",
        },
    ],
    "objects": [
        {
            "name": "widget",
            "attributes": [{"name": "id", "type": "string"}],
        }
    ],
}


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.router = Router()
        self.server, self.base = start_server(self.router)
        self.package = dict(PACKAGE)
        self.package["base_url"] = self.base + "/"
        self.package["pipeline_url"] = self.base + "/pipeline"

    def tearDown(self):
        self.server.shutdown()

    def _serve_package(self):
        self.router.add("POST", "/package", lambda body, query: (200, self.package))

    # -- basic round trip + dynamic dispatch -----------------------------------------

    def test_from_package_endpoint_round_trip_and_dynamic_dispatch(self):
        self._serve_package()
        self.router.add("POST", "/list-items", lambda body, query: (200, {"c": "d", "got": body}))

        client = wf.Client.from_package_endpoint(self.base + "/package")
        result = client.list_items(email="a@example.com")

        self.assertEqual(result["c"], "d")
        self.assertEqual(result["got"], {"email": "a@example.com"})
        client.close()

    def test_explicit_call_matches_dynamic_dispatch(self):
        self._serve_package()
        self.router.add("POST", "/list-items", lambda body, query: (200, {"c": "d"}))
        client = wf.Client.from_package_endpoint(self.base + "/package")
        self.assertEqual(client.call("list-items", {"email": "a@b.com"}), {"c": "d"})
        client.close()

    def test_unknown_attribute_raises(self):
        self._serve_package()
        client = wf.Client.from_package_endpoint(self.base + "/package")
        with self.assertRaises(AttributeError):
            client.this_endpoint_does_not_exist()
        client.close()

    # -- errors -----------------------------------------------------------------------

    def test_bad_request_error_triple(self):
        self._serve_package()
        self.router.add(
            "POST", "/list-items",
            lambda body, query: (400, ["WFN_NOT_FOUND", "Item not found", {"id": "123"}]),
        )
        client = wf.Client.from_package_endpoint(self.base + "/package")
        with self.assertRaises(wf.BadRequestError) as ctx:
            client.list_items(email="a@b.com")
        self.assertEqual(ctx.exception.code, "WFN_NOT_FOUND")
        self.assertEqual(ctx.exception.message, "Item not found")
        self.assertEqual(ctx.exception.details, {"id": "123"})
        client.close()

    def test_bad_request_generic_shape(self):
        self._serve_package()
        self.router.add("POST", "/list-items", lambda body, query: (400, {"unexpected": "shape"}))
        client = wf.Client.from_package_endpoint(self.base + "/package")
        with self.assertRaises(wf.BadRequestError) as ctx:
            client.list_items(email="a@b.com")
        self.assertEqual(ctx.exception.code, "WFN_BAD_REQUEST_ERROR")
        client.close()

    def test_unexpected_status_code(self):
        self._serve_package()
        self.router.add("POST", "/list-items", lambda body, query: (500, {"oops": True}))
        client = wf.Client.from_package_endpoint(self.base + "/package")
        with self.assertRaises(wf.UnexpectedStatusCodeError):
            client.list_items(email="a@b.com")
        client.close()

    # -- pagination ---------------------------------------------------------------------

    def test_pagination_next_and_previous(self):
        self._serve_package()

        def list_people(body, query):
            cursor = body.get("cursor", 0)
            pages = {
                0: {"page": [1, 2], "next": {"cursor": 1}, "previous": None},
                1: {"page": [3, 4], "next": None, "previous": {"cursor": 0}},
            }
            return 200, pages[cursor]

        self.router.add("POST", "/list-people", list_people)
        client = wf.Client.from_package_endpoint(self.base + "/package")

        page1 = client.list_people()
        self.assertIsInstance(page1, wf.Page)
        self.assertEqual(list(page1), [1, 2])
        self.assertTrue(page1.has_next)
        self.assertFalse(page1.has_previous)

        page2 = page1.next_page()
        self.assertEqual(list(page2), [3, 4])
        self.assertFalse(page2.has_next)
        self.assertTrue(page2.has_previous)

        page1_again = page2.previous_page()
        self.assertEqual(list(page1_again), [1, 2])
        client.close()

    def test_non_paginated_endpoint_not_wrapped_even_if_shape_matches(self):
        # Deliberate ecosystem-wide deviation from the Ruby gem: detection is via the
        # endpoint's `paginated` flag, not response-shape sniffing.
        self._serve_package()
        self.router.add(
            "POST", "/list-items",
            lambda body, query: (200, {"page": ["x"], "next": None, "previous": None}),
        )
        client = wf.Client.from_package_endpoint(self.base + "/package")
        result = client.list_items(email="a@b.com")
        self.assertNotIsInstance(result, wf.Page)
        self.assertEqual(result, {"page": ["x"], "next": None, "previous": None})
        client.close()

    # -- pipelining ---------------------------------------------------------------------

    def test_pipelining_round_trip_with_promise_field_reference(self):
        self._serve_package()

        def pipeline_handler(body, query):
            steps = body["steps"]
            results = []
            for step in steps:
                if step["url"].endswith("/list-items"):
                    results.append({"id": "abc123", "name": "widget"})
                elif step["url"].endswith("/get-widget"):
                    # the second step's body should have had the promise resolved
                    # to the literal JSONPath reference string (server resolves it)
                    self.assertEqual(step["body"].get("id"), "$[0].id")
                    results.append({"id": "abc123", "detail": "resolved"})
            return 200, results

        self.router.add("POST", "/pipeline", pipeline_handler)
        client = wf.Client.from_package_endpoint(self.base + "/package", pipelined=True)

        first = client.list_items(email="a@b.com")
        self.assertIsInstance(first, wf.Promise)

        with self.assertRaises(wf.UnresolvedPromiseError):
            _ = first.value

        second = client.get_widget(id=first["id"])
        results = client.pipeline.execute()

        self.assertEqual(results[0]["id"], "abc123")
        self.assertEqual(first.value, {"id": "abc123", "name": "widget"})
        self.assertEqual(second.value, {"id": "abc123", "detail": "resolved"})
        client.close()

    # -- from_url -------------------------------------------------------------------------

    def test_from_url_get_based_fetch_with_api_version_query_param(self):
        captured = {}

        def package_via_get(body, query):
            captured["query"] = query
            return 200, self.package

        self.router.add("GET", "/package.json", package_via_get)
        self.router.add("POST", "/list-items", lambda body, query: (200, {"ok": True}))

        client = wf.Client.from_url(self.base + "/package.json", version="2024-01-01")
        self.assertIn("api_version=2024-01-01", captured["query"])
        self.assertEqual(client.list_items(email="a@b.com"), {"ok": True})
        client.close()

    # -- objects --------------------------------------------------------------------------

    def test_package_object_context_lookup(self):
        self._serve_package()
        client = wf.Client.from_package_endpoint(self.base + "/package")
        pkg = client.package

        widget_in_attrs = pkg.object("widget", context="attributes")
        self.assertIsNotNone(widget_in_attrs)
        self.assertEqual([a.name for a in widget_in_attrs.attributes], ["id"])

        # "widget" defines no arguments, so it must be absent (None) in argument context.
        widget_in_args = pkg.object("widget", context="arguments")
        self.assertIsNone(widget_in_args)
        client.close()

    def test_endpoint_returns_object_reference(self):
        self._serve_package()
        client = wf.Client.from_package_endpoint(self.base + "/package")
        endpoint = client.package.endpoint("get_widget")
        self.assertIsNotNone(endpoint)
        self.assertEqual(endpoint.returns.objects, ["widget"])
        client.close()

    # -- gzip -----------------------------------------------------------------------------

    def test_gzip_response_is_transparently_decoded(self):
        # The mock server always gzips its response when Accept-Encoding: gzip is sent
        # (which the client always sends, per the wfn protocol) -- this is exactly the
        # scenario that broke webfunction-go and webfunction-java.
        self._serve_package()
        self.router.add("POST", "/list-items", lambda body, query: (200, {"c": "d"}))
        client = wf.Client.from_package_endpoint(self.base + "/package")
        self.assertEqual(client.list_items(email="a@b.com"), {"c": "d"})
        client.close()


class TypeValidationTests(unittest.TestCase):
    def test_email_refinement(self):
        t = wftype.parse("string.email")
        self.assertTrue(t.valid("a@b.com"))
        self.assertFalse(t.valid("not-an-email"))

    def test_u32_refinement(self):
        t = wftype.parse("number.u32")
        self.assertTrue(t.valid(42))
        self.assertFalse(t.valid(-1))
        self.assertFalse(t.valid(2 ** 32))

    def test_array_of_string(self):
        # A bare top-level list (e.g. ["string"]) is a *union* of types per the Ruby
        # gem's actual parse() semantics -- ["string"] alone collapses to plain
        # `string`, not array<string>. A nested list is what denotes "array of":
        t = wftype.parse([["string"]])
        self.assertTrue(t.valid(["a", "b"]))
        self.assertFalse(t.valid(["a", 1]))

    def test_bare_list_is_a_union_not_an_array(self):
        t = wftype.parse(["string", "number"])
        self.assertTrue(t.valid("a"))
        self.assertTrue(t.valid(1))
        self.assertFalse(t.valid(["a"]))

    def test_uuid_refinement(self):
        t = wftype.parse("string.uuid")
        self.assertTrue(t.valid("550e8400-e29b-41d4-a716-446655440000"))
        self.assertFalse(t.valid("not-a-uuid"))

    def test_ipv4_refinement(self):
        t = wftype.parse("string.ipv4")
        self.assertTrue(t.valid("192.168.1.1"))
        self.assertFalse(t.valid("not-an-ip"))
        self.assertFalse(t.valid("::1"))


class AsyncClientTests(unittest.TestCase):
    """A representative (not exhaustive) async mirror of the sync suite above --
    dynamic dispatch, pagination, and pipelining, run via asyncio.run()."""

    def setUp(self):
        self.router = Router()
        self.server, self.base = start_server(self.router)
        self.package = dict(PACKAGE)
        self.package["base_url"] = self.base + "/"
        self.package["pipeline_url"] = self.base + "/pipeline"

    def tearDown(self):
        self.server.shutdown()

    def _serve_package(self):
        self.router.add("POST", "/package", lambda body, query: (200, self.package))

    def test_async_round_trip_and_pagination(self):
        async def run():
            self._serve_package()
            self.router.add("POST", "/list-items", lambda body, query: (200, {"c": "d"}))

            def list_people(body, query):
                cursor = body.get("cursor", 0)
                pages = {
                    0: {"page": [1, 2], "next": {"cursor": 1}, "previous": None},
                    1: {"page": [3, 4], "next": None, "previous": {"cursor": 0}},
                }
                return 200, pages[cursor]

            self.router.add("POST", "/list-people", list_people)

            client = await wf.AsyncClient.from_package_endpoint(self.base + "/package")
            result = await client.list_items(email="a@b.com")
            self.assertEqual(result, {"c": "d"})

            page1 = await client.list_people()
            self.assertIsInstance(page1, wf.AsyncPage)
            self.assertEqual(list(page1), [1, 2])
            page2 = await page1.next_page()
            self.assertEqual(list(page2), [3, 4])

            await client.aclose()

        asyncio.run(run())

    def test_async_pipelining_round_trip(self):
        async def run():
            self._serve_package()

            def pipeline_handler(body, query):
                steps = body["steps"]
                results = []
                for step in steps:
                    if step["url"].endswith("/list-items"):
                        results.append({"id": "abc123"})
                    elif step["url"].endswith("/get-widget"):
                        self.assertEqual(step["body"].get("id"), "$[0].id")
                        results.append({"detail": "resolved"})
                return 200, results

            self.router.add("POST", "/pipeline", pipeline_handler)
            client = await wf.AsyncClient.from_package_endpoint(self.base + "/package", pipelined=True)

            first = await client.list_items(email="a@b.com")
            self.assertIsInstance(first, wf.Promise)
            second = await client.get_widget(id=first["id"])

            results = await client.pipeline.execute()
            self.assertEqual(results[0]["id"], "abc123")
            self.assertEqual(second.value, {"detail": "resolved"})

            await client.aclose()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
