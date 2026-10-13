"""Generic object applications and the type parameter ``T`` in the type grammar."""

from __future__ import annotations

import unittest

import webfunction as wf
from webfunction import wftype


def fmt(raw):
    return wftype.parse(raw).format()


class ExistingFormsUnchanged(unittest.TestCase):
    def test_existing_forms(self):
        cases = {
            "string": "string",
            "string.email": "string.email",
            "object.user": "object.user",
        }
        for raw, want in cases.items():
            self.assertEqual(fmt(raw), want, raw)
        self.assertEqual(fmt(["string", "null"]), "string | null")
        self.assertEqual(fmt([["string"]]), "array<string>")
        self.assertEqual(fmt([["object.person", "null"]]), "array<object.person | null>")
        self.assertEqual(fmt(["array", ["object.person"]]), "array<any> | array<object.person>")
        self.assertEqual(fmt(None), "any")


class Applications(unittest.TestCase):
    def test_single_application(self):
        t = wftype.parse({"object.list": "object.user"})
        self.assertEqual(t.format(), "object.list<object.user>")
        self.assertEqual(t.base_type, "object")
        self.assertEqual(t.refinement, "list")
        self.assertEqual(t.arg.format(), "object.user")
        self.assertEqual(t.format("compact"), "list")
        self.assertEqual(t.format("base"), "object")

    def test_union_nested_and_array_arguments(self):
        self.assertEqual(fmt({"object.list": ["object.user", "null"]}), "object.list<object.user | null>")
        self.assertEqual(fmt({"object.page": {"object.page": "object.user"}}), "object.page<object.page<object.user>>")
        self.assertEqual(fmt({"object.list": [["string"]]}), "object.list<array<string>>")
        self.assertEqual(wftype.parse({"object.page": {"object.page": "object.user"}}).objects, ["page", "user"])

    def test_inside_unions_and_arrays(self):
        self.assertEqual(fmt([{"object.list": "object.user"}, "null"]), "object.list<object.user> | null")
        self.assertEqual(fmt([[{"object.list": "object.user"}]]), "array<object.list<object.user>>")
        self.assertEqual(fmt([[{"object.list": "object.user"}, "null"]]), "array<object.list<object.user> | null>")
        self.assertEqual(fmt({"object.list": [{"object.pair": "number"}, "null"]}), "object.list<object.pair<number> | null>")

    def test_equality_includes_the_argument(self):
        a = wftype.parse({"object.list": "object.user"})
        self.assertEqual(a, wftype.parse({"object.list": "object.user"}))
        self.assertEqual(hash(a), hash(wftype.parse({"object.list": "object.user"})))
        self.assertNotEqual(a, wftype.parse({"object.list": "string"}))
        # A union keeps distinct applications of the same generic, and dedupes identical ones.
        self.assertEqual(fmt([{"object.list": "string"}, {"object.list": "number"}]), "object.list<string> | object.list<number>")
        self.assertEqual(fmt([{"object.list": "string"}, {"object.list": "string"}]), "object.list<string>")

    def test_valid_checks_for_an_object(self):
        t = wftype.parse({"object.list": "object.user"})
        self.assertTrue(t.valid({}))
        self.assertFalse(t.valid("nope"))


class Malformed(unittest.TestCase):
    def test_malformed_resolves_to_any_with_reason(self):
        cases = [
            ({}, wftype.MALFORMED_KEY_COUNT),
            ({"object.a": "string", "object.b": "string"}, wftype.MALFORMED_KEY_COUNT),
            ({"string": "object.user"}, wftype.MALFORMED_KEY_PREFIX),
            ({"list": "object.user"}, wftype.MALFORMED_KEY_PREFIX),
            ({"object.": "string"}, wftype.MALFORMED_KEY_PREFIX),
            ({"object.list": 5}, wftype.MALFORMED_ARGUMENT),
            ({"object.list": True}, wftype.MALFORMED_ARGUMENT),
        ]
        for raw, reason in cases:
            t = wftype.parse(raw)
            self.assertEqual(t.format(), "any", raw)
            self.assertEqual(t.malformed, reason, raw)
            self.assertTrue(t.valid("anything"), raw)
            self.assertTrue(t.valid({"x": 1}), raw)

    def test_malformed_entry_in_a_union_is_kept_as_any(self):
        t = wftype.parse([{"string": "x"}, "null"])
        self.assertEqual(t.format(), "any | null")
        self.assertEqual(t.members[0].malformed, wftype.MALFORMED_KEY_PREFIX)

    def test_well_formed_types_are_not_malformed(self):
        self.assertIsNone(wftype.parse("string").malformed)
        self.assertIsNone(wftype.parse({"object.list": "string"}).malformed)
        self.assertIsNone(wftype.any_type().malformed)


class TypeParameter(unittest.TestCase):
    def test_t_resolves_to_any(self):
        self.assertEqual(fmt("T"), "any")
        self.assertEqual(fmt([["T"]]), "array<any>")
        self.assertEqual(fmt(["T", "null"]), "any | null")
        self.assertTrue(wftype.parse("T").valid("anything"))
        self.assertTrue(wftype.parse("T").valid({"x": 1}))

    def test_t_is_marked_for_tooling(self):
        t = wftype.parse("T")
        self.assertEqual(t.base_type, "any")
        self.assertTrue(t.param)
        self.assertTrue(wftype.parse([["T"]]).of.param)
        self.assertTrue(wftype.parse(["T", "null"]).members[0].param)

    def test_only_the_bare_token_is_a_parameter(self):
        self.assertFalse(wftype.parse("any").param)
        self.assertFalse(wftype.any_type().param)
        self.assertFalse(wftype.parse("object.T").param)
        self.assertEqual(fmt("object.T"), "object.T")


class PackageWithGenerics(unittest.TestCase):
    def test_package_loads(self):
        pkg = wf.Package.from_dict(
            {
                "base_url": "https://api.example.com/",
                "endpoints": [
                    {
                        "name": "list-users",
                        "returns": {"object.list": "object.user"},
                        "arguments": [{"name": "filter", "type": [{"object.pair": "string"}, "null"]}],
                    },
                    {"name": "broken", "returns": {}, "arguments": []},
                ],
                "objects": [
                    {
                        "name": "list",
                        "attributes": [
                            {"name": "total", "type": "number"},
                            {"name": "items", "type": [["T"]]},
                        ],
                    }
                ],
            }
        )
        ep = pkg.endpoint("list-users")
        self.assertEqual(ep.returns.format(), "object.list<object.user>")
        self.assertEqual(ep.argument("filter").type.format(), "object.pair<string> | null")
        self.assertEqual(pkg.endpoint("broken").returns.format(), "any")
        self.assertEqual(pkg.object("list", context="attributes").attribute("items").type.format(), "array<any>")


if __name__ == "__main__":
    unittest.main()