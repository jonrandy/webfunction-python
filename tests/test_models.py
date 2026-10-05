"""Unit tests for the parsed package model (no HTTP involved)."""

from __future__ import annotations

import unittest

import webfunction as wf


class PrivateFlagTests(unittest.TestCase):
    def setUp(self):
        self.pkg = wf.Package.from_dict(
            {
                "base_url": "https://api.example.com/",
                "endpoints": [
                    {"name": "internal-sync", "returns": "boolean", "flags": ["private"]},
                    {
                        "name": "find-account",
                        "returns": "object",
                        "arguments": [
                            {"name": "id", "type": "string", "flags": ["required"]},
                            {"name": "debug", "type": "boolean", "flags": ["private"]},
                        ],
                        "attributes": [
                            {"name": "email", "type": "string"},
                            {"name": "audit_ref", "type": "string", "flags": ["private"]},
                        ],
                    },
                ],
            }
        )

    def test_endpoint_private(self):
        self.assertTrue(self.pkg.endpoint("internal-sync").private)
        self.assertFalse(self.pkg.endpoint("find-account").private)

    def test_argument_private(self):
        endpoint = self.pkg.endpoint("find-account")
        self.assertTrue(endpoint.argument("debug").private)
        self.assertFalse(endpoint.argument("id").private)

    def test_attribute_private(self):
        endpoint = self.pkg.endpoint("find-account")
        self.assertTrue(endpoint.attribute("audit_ref").private)
        self.assertFalse(endpoint.attribute("email").private)


if __name__ == "__main__":
    unittest.main()