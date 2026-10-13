"""The Web Function type grammar, ported from the Ruby reference gem's ``type.rb``.

Every type node supports ``.format(fmt)``, ``.valid(value)``, ``.objects``, and
``.without_refinements()``, mirroring the Ruby/Go/Java/C# clients' Type classes.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any, List, Optional, Union as _TypingUnion
from urllib.parse import urlparse

ALLOWED_REFINEMENTS = {
    "number": {"u32", "u64", "i32", "i64", "f32", "f64", "timestamp"},
    "string": {
        "date", "time", "datetime", "uuid", "base64", "email", "phone",
        "url", "uri", "ipv4", "ipv6", "hostname",
    },
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}(\.\d+)?$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$")
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+[1-9]\d{1,14}$")
_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _v_u32(v): return _is_int(v) and 0 <= v <= 0xFFFFFFFF
def _v_u64(v): return _is_int(v) and 0 <= v <= 0xFFFFFFFFFFFFFFFF
def _v_i32(v): return _is_int(v) and -0x80000000 <= v <= 0x7FFFFFFF
def _v_i64(v): return _is_int(v) and -0x8000000000000000 <= v <= 0x7FFFFFFFFFFFFFFF


def _v_f32(v):
    if not _is_number(v):
        return False
    f = float(v)
    return f == f and f not in (float("inf"), float("-inf")) and abs(f) <= 3.4028235e38


def _v_f64(v):
    if not _is_number(v):
        return False
    f = float(v)
    return f == f and f not in (float("inf"), float("-inf"))


def _v_timestamp(v): return _is_int(v) and v >= 0
def _v_date(v): return isinstance(v, str) and bool(_DATE_RE.match(v))
def _v_time(v): return isinstance(v, str) and bool(_TIME_RE.match(v))
def _v_datetime(v): return isinstance(v, str) and bool(_DATETIME_RE.match(v))
def _v_uuid(v): return isinstance(v, str) and bool(_UUID_RE.match(v))
def _v_base64(v): return isinstance(v, str) and len(v) % 4 == 0 and bool(_BASE64_RE.match(v))
def _v_email(v): return isinstance(v, str) and bool(_EMAIL_RE.match(v))
def _v_phone(v): return isinstance(v, str) and bool(_PHONE_RE.match(v))


def _v_url(v):
    if not isinstance(v, str):
        return False
    try:
        parsed = urlparse(v)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except ValueError:
        return False


def _v_uri(v):
    if not isinstance(v, str):
        return False
    try:
        return bool(urlparse(v).scheme)
    except ValueError:
        return False


def _v_ipv4(v):
    if not isinstance(v, str):
        return False
    try:
        ipaddress.IPv4Address(v)
        return True
    except ValueError:
        return False


def _v_ipv6(v):
    if not isinstance(v, str):
        return False
    try:
        ipaddress.IPv6Address(v)
        return True
    except ValueError:
        return False


def _v_hostname(v): return isinstance(v, str) and bool(_HOSTNAME_RE.match(v))


REFINEMENT_VALIDATORS = {
    "u32": _v_u32, "u64": _v_u64, "i32": _v_i32, "i64": _v_i64,
    "f32": _v_f32, "f64": _v_f64, "timestamp": _v_timestamp,
    "date": _v_date, "time": _v_time, "datetime": _v_datetime,
    "uuid": _v_uuid, "base64": _v_base64, "email": _v_email, "phone": _v_phone,
    "url": _v_url, "uri": _v_uri, "ipv4": _v_ipv4, "ipv6": _v_ipv6, "hostname": _v_hostname,
}


# Reasons recorded in ``Type.malformed`` for an invalid generic application. Such a type
# resolves to ``any`` (so a package using generics, even incorrectly, still loads) and
# keeps the reason so validation tooling can still report it.
MALFORMED_KEY_COUNT = "key-count"  # the application object did not have exactly one key
MALFORMED_KEY_PREFIX = "key-prefix"  # the key was not "object.<name>"
MALFORMED_ARGUMENT = "argument"  # the value was not a valid type


class Type:
    """Base class for all type nodes. Not instantiated directly."""

    base_type: Optional[str] = None
    refinement: Optional[str] = None
    # The type argument when this is a generic object applied to a type
    # ({"object.list": "object.user"} is object.list with arg object.user). None otherwise.
    arg: Optional["Type"] = None
    # One of the MALFORMED_* reasons for an invalid generic application (parsed as ``any``).
    malformed: Optional[str] = None
    # True for the generic type parameter token "T". It is ``any`` to every consumer; this
    # only lets tooling that expands generics tell it from a literal ``any``.
    param: bool = False

    def format(self, fmt: str = "default") -> str:
        raise NotImplementedError

    def valid(self, value: Any) -> bool:
        raise NotImplementedError

    @property
    def objects(self) -> List[str]:
        return []

    def without_refinements(self) -> "Type":
        return self

    def __str__(self) -> str:
        return self.format()


class BaseTypeNode(Type):
    def __init__(self, base_type: str, refinement: Optional[str] = None, arg: Optional[Type] = None):
        self.base_type = base_type
        self.refinement = refinement
        self.arg = arg

    def format(self, fmt: str = "default") -> str:
        if fmt == "compact":
            return self.refinement or self.base_type
        if fmt == "base":
            return self.base_type
        text = f"{self.base_type}.{self.refinement}" if self.refinement else self.base_type
        if self.arg is not None:
            text += f"<{self.arg.format(fmt)}>"
        return text

    def __eq__(self, other):
        return (
            isinstance(other, BaseTypeNode)
            and other.base_type == self.base_type
            and other.refinement == self.refinement
            and other.arg == self.arg
        )

    def __hash__(self):
        return hash((BaseTypeNode, self.base_type, self.refinement, self.arg))

    def __repr__(self):
        text = f"<{self.base_type} {self.refinement}>" if self.refinement else f"<{self.base_type}>"
        return text if self.arg is None else f"{text[:-1]} of {self.arg!r}>"

    @property
    def objects(self) -> List[str]:
        names = [self.refinement] if self.base_type == "object" and self.refinement else []
        if self.arg is not None:
            names += [o for o in self.arg.objects if o not in names]
        return names

    def without_refinements(self) -> "Type":
        return self if self.refinement is None else BaseTypeNode(self.base_type)

    def valid(self, value: Any) -> bool:
        if self.base_type == "string":
            return isinstance(value, str) and self._refinement_valid(value)
        if self.base_type == "number":
            return _is_number(value) and self._refinement_valid(value)
        if self.base_type == "object":
            return isinstance(value, dict)
        if self.base_type == "boolean":
            return isinstance(value, bool)
        if self.base_type == "null":
            return value is None
        return False

    def _refinement_valid(self, value: Any) -> bool:
        if self.refinement is None:
            return True
        return REFINEMENT_VALIDATORS[self.refinement](value)


class ArrayType(Type):
    def __init__(self, of: Type):
        self.base_type = "array"
        self.of = of

    def format(self, fmt: str = "default") -> str:
        if fmt == "base":
            return "array"
        return f"array<{self.of.format(fmt)}>"

    def __eq__(self, other):
        return isinstance(other, ArrayType) and other.of == self.of

    def __hash__(self):
        return hash((ArrayType, self.of))

    def __repr__(self):
        return f"<ArrayOf {self.of!r}>"

    @property
    def objects(self) -> List[str]:
        return self.of.objects

    def without_refinements(self) -> "Type":
        return ArrayType(self.of.without_refinements())

    def valid(self, value: Any) -> bool:
        return isinstance(value, list) and all(self.of.valid(v) for v in value)


class UnionType(Type):
    def __init__(self, members: List[Type]):
        self.members = members

    def format(self, fmt: str = "default") -> str:
        return " | ".join(m.format(fmt) for m in self.members)

    def __eq__(self, other):
        return isinstance(other, UnionType) and other.members == self.members

    def __hash__(self):
        return hash((UnionType, tuple(self.members)))

    def __repr__(self):
        return f"<Union {' | '.join(repr(m) for m in self.members)}>"

    @property
    def objects(self) -> List[str]:
        seen, result = set(), []
        for m in self.members:
            for o in m.objects:
                if o not in seen:
                    seen.add(o)
                    result.append(o)
        return result

    def without_refinements(self) -> "Type":
        return union_of([m.without_refinements() for m in self.members])

    def valid(self, value: Any) -> bool:
        return any(m.valid(value) for m in self.members)


class AnyType(Type):
    base_type = "any"

    def __init__(self, *, param: bool = False, malformed: Optional[str] = None):
        self.param = param
        self.malformed = malformed

    def format(self, fmt: str = "default") -> str:
        return "any"

    def __eq__(self, other):
        return isinstance(other, AnyType)

    def __hash__(self):
        return hash(AnyType)

    def __repr__(self):
        return "<any>"

    def valid(self, value: Any) -> bool:
        return True


def any_type() -> Type: return AnyType()
def param_type() -> Type: return AnyType(param=True)
def string_type(refinement: Optional[str] = None) -> Type: return BaseTypeNode("string", refinement)
def number_type(refinement: Optional[str] = None) -> Type: return BaseTypeNode("number", refinement)
def object_type(refinement: Optional[str] = None) -> Type: return BaseTypeNode("object", refinement)
def array_type(of: Optional[Type] = None) -> Type: return ArrayType(of if of is not None else any_type())
def boolean_type() -> Type: return BaseTypeNode("boolean")
def null_type() -> Type: return BaseTypeNode("null")


def union_of(types: List[Type]) -> Type:
    uniq: List[Type] = []
    for t in types:
        if t not in uniq:
            uniq.append(t)
    if len(uniq) > 1:
        return UnionType(uniq)
    return uniq[0]


def _base(type_str: str) -> Optional[Type]:
    if type_str == "T":
        return param_type()
    base_type, _, refinement = type_str.partition(".")
    refinement = refinement or None

    if base_type == "string":
        if refinement and refinement not in ALLOWED_REFINEMENTS["string"]:
            return string_type()
        return string_type(refinement)
    if base_type == "number":
        if refinement and refinement not in ALLOWED_REFINEMENTS["number"]:
            return number_type()
        return number_type(refinement)
    if base_type == "object":
        return object_type(refinement)
    if base_type == "array":
        return array_type()
    if base_type == "boolean":
        return boolean_type()
    if base_type == "null":
        return null_type()
    if base_type == "any":
        return any_type()
    return None


def _application(raw: dict) -> Type:
    """Parses a generic application, {"object.<name>": <type>}. Anything that is not exactly
    that shape resolves to ``any`` carrying the reason in ``malformed``, rather than failing."""
    if len(raw) != 1:
        return AnyType(malformed=MALFORMED_KEY_COUNT)
    (key, value), = raw.items()
    if not isinstance(key, str) or not key.startswith("object.") or key == "object.":
        return AnyType(malformed=MALFORMED_KEY_PREFIX)
    if isinstance(value, (bool, int, float)):
        return AnyType(malformed=MALFORMED_ARGUMENT)
    return BaseTypeNode("object", key[len("object."):], parse(value))


def _detect(raw: Any) -> Optional[Type]:
    if isinstance(raw, str):
        return _base(raw)
    if isinstance(raw, dict):
        return _application(raw)
    if isinstance(raw, list):
        types = [t for t in (_detect(r) for r in raw) if t is not None]
        if not types:
            return array_type(any_type())
        return array_type(union_of(types))
    return None


def parse(raw: _TypingUnion[str, List[Any], None]) -> Type:
    """Parses a wfn ``type`` value (a string, a generic application object, or an array of
    strings/arrays/application objects) into a Type node."""
    items = raw if isinstance(raw, list) else ([raw] if raw is not None else [])
    types = [t for t in (_detect(r) for r in items) if t is not None]
    if not types:
        return any_type()
    return union_of(types)