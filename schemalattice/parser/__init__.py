"""
Parser: turns a .sl.yaml schema definition into the IR defined in ir.py.

Schema DSL shape (see examples/ for full files):

    namespace: com.example.orders
    version: "1.2.0"
    record:
      name: Order
      doc: "A single customer order"
      fields:
        - name: order_id
          type: string
          required: true
        - name: total_cents
          type: long
        - name: status
          type: enum
          values: [PENDING, PAID, SHIPPED, CANCELLED]
        - name: items
          type: array
          items:
            type: record
            name: OrderItem
            fields:
              - name: sku
                type: string
              - name: qty
                type: int
                default: 1
        - name: metadata
          type: map
          values:
            type: string
          required: false
"""

from __future__ import annotations

import yaml

from ..ir import EnumType, Field, FieldKind, RecordType, Schema

_PRIMITIVE_NAMES = {k.value for k in FieldKind if k.value not in ("enum", "record", "array", "map")}


class SchemaParseError(ValueError):
    pass


def parse_schema_file(path: str) -> Schema:
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return parse_schema_dict(raw)


def parse_schema_dict(raw: dict) -> Schema:
    if "record" not in raw:
        raise SchemaParseError("schema file must have a top-level 'record' key")

    namespace = raw.get("namespace", "schemalattice.generated")
    version = raw.get("version", "1.0.0")
    root = _parse_record(raw["record"])
    root.namespace = namespace
    return Schema(root=root, namespace=namespace, version=version)


def _default_record_type_name(field_name: str) -> str:
    parts = field_name.split("_")
    return "".join(p.capitalize() for p in parts)


def _parse_inline_record(node: dict, default_type_name: str, allow_name_as_type: bool = False) -> RecordType:
    """Parse a record type nested inside a field definition.

    For a field like `- name: user, type: record, record_name: UserRef`,
    'name' is the FIELD name and must never be used as the record TYPE
    name — that's what causes the type name to silently clobber the field
    name. 'record_name' (or a PascalCase default derived from the field
    name) is used instead.

    For array/map items there's no separate field-name in play (the
    synthetic name is internal-only), so passing allow_name_as_type=True
    lets 'name' double as the type name there, e.g.
    `items: {type: record, name: OrderItem, fields: [...]}`.
    """
    if allow_name_as_type:
        type_name = node.get("record_name", node.get("name", default_type_name))
    else:
        type_name = node.get("record_name", default_type_name)
    fields_raw = node.get("fields", [])
    fields = [_parse_field(f) for f in fields_raw]
    return RecordType(name=type_name, fields=fields, doc=node.get("doc"))


def _parse_record(node: dict) -> RecordType:
    name = node.get("name")
    if not name:
        raise SchemaParseError("record is missing required 'name'")
    fields_raw = node.get("fields", [])
    fields = [_parse_field(f) for f in fields_raw]
    return RecordType(name=name, fields=fields, doc=node.get("doc"))


def _parse_field(node: dict, _in_collection_item: bool = False) -> Field:
    name = node.get("name")
    if not name:
        raise SchemaParseError("field is missing required 'name'")

    type_name = node.get("type")
    if not type_name:
        raise SchemaParseError(f"field '{name}' is missing required 'type'")

    required = node.get("required", True)
    doc = node.get("doc")
    has_default = "default" in node
    default = node.get("default")

    if type_name in _PRIMITIVE_NAMES:
        kind = FieldKind(type_name)
        return Field(
            name=name, kind=kind, doc=doc, required=required,
            default=default, has_default=has_default,
        )

    if type_name == "enum":
        values = node.get("values")
        if not values:
            raise SchemaParseError(f"enum field '{name}' must define 'values'")
        enum_type = EnumType(name=_enum_type_name(name), values=values, doc=doc)
        return Field(
            name=name, kind=FieldKind.ENUM, doc=doc, required=required,
            default=default, has_default=has_default, enum=enum_type,
        )

    if type_name == "record":
        record = _parse_inline_record(
            node,
            default_type_name=_default_record_type_name(name),
            allow_name_as_type=_in_collection_item,
        )
        return Field(
            name=name, kind=FieldKind.RECORD, doc=doc, required=required,
            record=record,
        )

    if type_name == "array":
        items_node = node.get("items")
        if not items_node:
            raise SchemaParseError(f"array field '{name}' must define 'items'")
        item_node = dict(items_node)
        item_node.setdefault("name", f"{name}_item")
        item_field = _parse_field(item_node, _in_collection_item=True)
        return Field(
            name=name, kind=FieldKind.ARRAY, doc=doc, required=required,
            item=item_field,
        )

    if type_name == "map":
        values_node = node.get("values")
        if not values_node:
            raise SchemaParseError(f"map field '{name}' must define 'values'")
        value_node = dict(values_node)
        value_node.setdefault("name", f"{name}_value")
        value_field = _parse_field(value_node, _in_collection_item=True)
        return Field(
            name=name, kind=FieldKind.MAP, doc=doc, required=required,
            item=value_field,
        )

    raise SchemaParseError(f"field '{name}' has unknown type '{type_name}'")


def _enum_type_name(field_name: str) -> str:
    # OrderStatus from "status" -> reasonably-named generated enum type
    parts = field_name.split("_")
    return "".join(p.capitalize() for p in parts) + "Enum"
