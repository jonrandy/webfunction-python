"""Package/Endpoint/Argument/Attribute/ObjectSchema/DocumentedError, ported from the
Ruby reference gem's package.rb/endpoint.rb/argument.rb/attribute.rb/object_schema.rb/
documented_error.rb/flaggable.rb.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import wftype


def _normalize_array(items: Any, fn=None) -> list:
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        value = fn(item) if fn else item
        if value is not None:
            result.append(value)
    return result


def _normalize_strings(items: Any) -> List[str]:
    return _normalize_array(items, lambda i: str(i))


def _normalize_choices(raw: Any) -> list:
    if isinstance(raw, list):
        return list(raw)
    return [raw] if raw is not None else []


class Flaggable:
    """Mixin providing ``has_flag()`` for objects with a ``flags`` list, mirroring the
    Ruby gem's ``Flaggable`` module."""

    flags: List[str]

    def has_flag(self, flag: str) -> bool:
        return flag in self.flags


@dataclass
class DocumentedError:
    code: str
    docs: str = ""

    @classmethod
    def from_dict(cls, d: Any) -> Optional["DocumentedError"]:
        if not isinstance(d, dict) or not d.get("code"):
            return None
        return cls(code=d["code"], docs=str(d.get("docs") or ""))

    @classmethod
    def from_list(cls, items: Any) -> List["DocumentedError"]:
        return _normalize_array(items, cls.from_dict)


@dataclass
class Argument(Flaggable):
    name: str
    type: wftype.Type
    group: Optional[str] = None
    choices: list = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    docs: str = ""

    @property
    def required(self) -> bool:
        return self.has_flag("required")

    @property
    def optional(self) -> bool:
        return not self.required

    @classmethod
    def from_dict(cls, d: Any) -> Optional["Argument"]:
        if not isinstance(d, dict) or not d.get("name") or not d.get("type"):
            return None
        return cls(
            name=d["name"],
            type=wftype.parse(d["type"]),
            group=d.get("group"),
            choices=_normalize_choices(d.get("choices")),
            flags=_normalize_strings(d.get("flags")),
            docs=str(d.get("docs") or ""),
        )

    @classmethod
    def from_list(cls, items: Any) -> List["Argument"]:
        return _normalize_array(items, cls.from_dict)


@dataclass
class Attribute(Flaggable):
    name: str
    type: wftype.Type
    values: list = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    docs: str = ""

    @property
    def nullable(self) -> bool:
        return self.has_flag("nullable")

    @classmethod
    def from_dict(cls, d: Any) -> Optional["Attribute"]:
        if not isinstance(d, dict) or not d.get("name") or not d.get("type"):
            return None
        return cls(
            name=d["name"],
            type=wftype.parse(d["type"]),
            values=_normalize_choices(d.get("values")),
            flags=_normalize_strings(d.get("flags")),
            docs=str(d.get("docs") or ""),
        )

    @classmethod
    def from_list(cls, items: Any) -> List["Attribute"]:
        return _normalize_array(items, cls.from_dict)


class ObjectSchema:
    """Named object definition. An ``object.<name>`` reference resolves against either
    its ``arguments`` (argument context) or ``attributes`` (attribute context)."""

    CONTEXTS = ("arguments", "attributes")

    def __init__(self, name: str, arguments: Optional[List[Argument]] = None,
                 attributes: Optional[List[Attribute]] = None):
        self.name = name
        self._arguments: Dict[str, Argument] = {a.name: a for a in (arguments or [])}
        self._attributes: Dict[str, Attribute] = {a.name: a for a in (attributes or [])}

    @property
    def arguments(self) -> List[Argument]:
        return list(self._arguments.values())

    def argument(self, name: str) -> Optional[Argument]:
        return self._arguments.get(str(name))

    @property
    def attributes(self) -> List[Attribute]:
        return list(self._attributes.values())

    def attribute(self, name: str) -> Optional[Attribute]:
        return self._attributes.get(str(name))

    def properties(self, context: str) -> list:
        if context == "arguments":
            return self.arguments
        if context == "attributes":
            return self.attributes
        raise ValueError(f"context must be one of {self.CONTEXTS!r}, got {context!r}")

    def __repr__(self):
        return f"ObjectSchema(name={self.name!r})"

    @classmethod
    def from_dict(cls, d: Any) -> Optional["ObjectSchema"]:
        if not isinstance(d, dict) or not d.get("name"):
            return None
        return cls(
            name=d["name"],
            arguments=Argument.from_list(d.get("arguments")),
            attributes=Attribute.from_list(d.get("attributes")),
        )

    @classmethod
    def from_list(cls, items: Any) -> List["ObjectSchema"]:
        return _normalize_array(items, cls.from_dict)


class Endpoint(Flaggable):
    def __init__(self, *, name: str, returns: Any, flags: Optional[List[str]] = None,
                 group: Optional[str] = None, docs: Optional[str] = None,
                 arguments: Optional[List[Argument]] = None,
                 attributes: Optional[List[Attribute]] = None,
                 errors: Optional[List[DocumentedError]] = None):
        self.name = name
        self.returns = wftype.parse(returns)
        self.flags = flags or []
        self.group = group
        self.docs = docs or ""
        self._arguments: Dict[str, Argument] = {a.name: a for a in (arguments or [])}
        self._attributes: Dict[str, Attribute] = {a.name: a for a in (attributes or [])}
        self._errors: Dict[str, DocumentedError] = {e.code: e for e in (errors or [])}
        # Assigned when the endpoint is loaded from a package into a Client; required by .call().
        self.client = None

    @property
    def arguments(self) -> List[Argument]:
        return list(self._arguments.values())

    def argument(self, name: str) -> Optional[Argument]:
        return self._arguments.get(str(name))

    @property
    def attributes(self) -> List[Attribute]:
        return list(self._attributes.values())

    def attribute(self, name: str) -> Optional[Attribute]:
        return self._attributes.get(str(name))

    @property
    def errors(self) -> List[DocumentedError]:
        return list(self._errors.values())

    def error(self, code: str) -> Optional[DocumentedError]:
        return self._errors.get(str(code))

    @property
    def bearer_auth(self) -> bool:
        return self.has_flag("bearer_auth")

    @property
    def capture_bearer(self) -> bool:
        return self.has_flag("capture_bearer")

    @property
    def paginated(self) -> bool:
        return self.has_flag("paginated")

    @property
    def private(self) -> bool:
        return self.has_flag("private")

    def call(self, **args) -> Any:
        if self.client is None:
            raise RuntimeError("client must be set to invoke an endpoint")
        return self.client.call(self.name, args)

    def __repr__(self):
        return f"Endpoint(name={self.name!r})"

    @classmethod
    def from_dict(cls, d: Any) -> Optional["Endpoint"]:
        if not isinstance(d, dict) or not d.get("name") or not d.get("returns"):
            return None
        return cls(
            name=d["name"],
            returns=d["returns"],
            flags=_normalize_strings(d.get("flags")),
            group=d.get("group"),
            docs=str(d.get("docs") or ""),
            arguments=Argument.from_list(d.get("arguments")),
            attributes=Attribute.from_list(d.get("attributes")),
            errors=DocumentedError.from_list(d.get("errors")),
        )

    @classmethod
    def from_list(cls, items: Any) -> List["Endpoint"]:
        return _normalize_array(items, cls.from_dict)


class Package(Flaggable):
    def __init__(self, *, base_url: str, pipeline_url: Optional[str] = None,
                 name: Optional[str] = None, version: Optional[str] = None,
                 docs: Optional[str] = None, flags: Optional[List[str]] = None,
                 versions: Optional[List[str]] = None,
                 endpoints: Optional[List[Endpoint]] = None,
                 errors: Optional[List[DocumentedError]] = None,
                 objects: Optional[List[ObjectSchema]] = None):
        self.base_url = base_url
        self.pipeline_url = pipeline_url
        self.name = name
        self.version = version
        self.docs = docs or ""
        self.flags = flags or []
        self.versions = versions or []
        self._endpoints: Dict[str, Endpoint] = {e.name: e for e in (endpoints or [])}
        self._errors: Dict[str, DocumentedError] = {e.code: e for e in (errors or [])}
        self._objects: Dict[str, ObjectSchema] = {o.name: o for o in (objects or [])}

    @property
    def endpoints(self) -> List[Endpoint]:
        return list(self._endpoints.values())

    def endpoint(self, name: str) -> Optional[Endpoint]:
        # Underscores map to hyphens so python_style_names match hyphenated endpoint names.
        return self._endpoints.get(str(name).replace("_", "-"))

    @property
    def errors(self) -> List[DocumentedError]:
        return list(self._errors.values())

    def error(self, code: str) -> Optional[DocumentedError]:
        return self._errors.get(str(code))

    @property
    def objects(self) -> List[ObjectSchema]:
        return list(self._objects.values())

    def object(self, name: str, *, context: str) -> Optional[ObjectSchema]:
        obj = self._objects.get(str(name))
        if obj is None:
            return None
        if not obj.properties(context):
            return None
        return obj

    @property
    def versioned(self) -> bool:
        return self.has_flag("versioned")

    def __repr__(self):
        return f"Package(name={self.name!r}, base_url={self.base_url!r})"

    @classmethod
    def from_dict(cls, d: Any) -> "Package":
        d = d or {}
        return cls(
            base_url=d.get("base_url"),
            pipeline_url=d.get("pipeline_url"),
            name=d.get("name"),
            version=d.get("version"),
            docs=str(d.get("docs") or ""),
            flags=_normalize_strings(d.get("flags")),
            versions=_normalize_strings(d.get("versions")),
            endpoints=Endpoint.from_list(d.get("endpoints")),
            errors=DocumentedError.from_list(d.get("errors")),
            objects=ObjectSchema.from_list(d.get("objects")),
        )
