"""Generates an Avro schema (.avsc, as a dict) from the IR.

Avro has no native "optional with default None" concept the way JSON Schema
does — instead, optionality is expressed as a union with "null", and a
default value of null. We follow that convention here.
"""

from __future__ import annotations

from ..ir import Field, FieldKind, RecordType, Schema

_PRIMITIVE_MAP = {
    FieldKind.STRING: "string",
    FieldKind.INT: "int",
    FieldKind.LONG: "long",
    FieldKind.FLOAT: "float",
    FieldKind.DOUBLE: "double",
    FieldKind.BOOL: "boolean",
    FieldKind.BYTES: "bytes",
    # Avro logical type: long epoch-millis tagged as timestamp-millis
    FieldKind.TIMESTAMP: {"type": "long", "logicalType": "timestamp-millis"},
}


def generate(schema: Schema) -> dict:
    return _record_to_avro(schema.root, schema.namespace)


def _record_to_avro(record: RecordType, namespace: str) -> dict:
    out = {
        "type": "record",
        "name": record.name,
        "namespace": namespace,
        "fields": [_field_to_avro(f, namespace) for f in record.fields],
    }
    if record.doc:
        out["doc"] = record.doc
    return out


def _field_to_avro(f: Field, namespace: str) -> dict:
    base_type = _type_for(f, namespace)

    if not f.required:
        # Optional -> union with null, default null (unless an explicit
        # default was given in the schema definition).
        avro_type = ["null", base_type]
        default = None if not f.has_default else f.default
        out = {"name": f.name, "type": avro_type, "default": default}
    else:
        out = {"name": f.name, "type": base_type}
        if f.has_default:
            out["default"] = f.default

    if f.doc:
        out["doc"] = f.doc
    return out


def _type_for(f: Field, namespace: str):
    if f.kind in _PRIMITIVE_MAP:
        return _PRIMITIVE_MAP[f.kind]
    if f.kind == FieldKind.ENUM:
        return {
            "type": "enum",
            "name": f.enum.name,
            "namespace": namespace,
            "symbols": list(f.enum.values),
        }
    if f.kind == FieldKind.RECORD:
        return _record_to_avro(f.record, namespace)
    if f.kind == FieldKind.ARRAY:
        return {"type": "array", "items": _type_for(f.item, namespace)}
    if f.kind == FieldKind.MAP:
        return {"type": "map", "values": _type_for(f.item, namespace)}
    raise ValueError(f"unhandled field kind: {f.kind}")
