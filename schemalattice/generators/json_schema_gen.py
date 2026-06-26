"""Generates a JSON Schema (draft 2020-12) document from the IR."""

from __future__ import annotations

from ..ir import Field, FieldKind, RecordType, Schema

_PRIMITIVE_MAP = {
    FieldKind.STRING: {"type": "string"},
    FieldKind.INT: {"type": "integer"},
    FieldKind.LONG: {"type": "integer"},
    FieldKind.FLOAT: {"type": "number"},
    FieldKind.DOUBLE: {"type": "number"},
    FieldKind.BOOL: {"type": "boolean"},
    FieldKind.BYTES: {"type": "string", "contentEncoding": "base64"},
    FieldKind.TIMESTAMP: {"type": "string", "format": "date-time"},
}


def generate(schema: Schema) -> dict:
    """Returns a plain dict — caller decides whether to json.dump it."""
    root_schema = _record_to_schema(schema.root, schema)
    root_schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    root_schema["$id"] = f"{schema.namespace}.{schema.root.name}"
    return root_schema


def _record_to_schema(record: RecordType, schema: Schema) -> dict:
    properties = {}
    required = []
    for f in record.fields:
        properties[f.name] = _field_to_schema(f, schema)
        if f.required:
            required.append(f.name)

    out = {"type": "object", "properties": properties}
    if required:
        out["required"] = required
    if record.doc:
        out["description"] = record.doc
    out["additionalProperties"] = False
    return out


def _field_to_schema(f: Field, schema: Schema) -> dict:
    if f.kind in _PRIMITIVE_MAP:
        out = dict(_PRIMITIVE_MAP[f.kind])
    elif f.kind == FieldKind.ENUM:
        out = {"type": "string", "enum": list(f.enum.values)}
    elif f.kind == FieldKind.RECORD:
        out = _record_to_schema(f.record, schema)
    elif f.kind == FieldKind.ARRAY:
        out = {"type": "array", "items": _field_to_schema(f.item, schema)}
    elif f.kind == FieldKind.MAP:
        out = {"type": "object", "additionalProperties": _field_to_schema(f.item, schema)}
    else:
        raise ValueError(f"unhandled field kind: {f.kind}")

    if f.doc:
        out["description"] = f.doc
    if f.has_default:
        out["default"] = f.default
    return out
