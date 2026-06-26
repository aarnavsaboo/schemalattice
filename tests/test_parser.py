"""Unit tests for the schema parser — error handling and edge cases
that the round-trip tests don't exercise."""

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemalattice.ir import FieldKind
from schemalattice.parser import SchemaParseError, parse_schema_dict


def _parse(yaml_text: str):
    return parse_schema_dict(yaml.safe_load(yaml_text))


def test_missing_record_key_raises():
    with pytest.raises(SchemaParseError, match="top-level 'record'"):
        _parse("namespace: foo\nversion: '1.0'\n")


def test_record_without_name_raises():
    with pytest.raises(SchemaParseError, match="missing required 'name'"):
        _parse("record:\n  fields: []\n")


def test_field_without_type_raises():
    with pytest.raises(SchemaParseError, match="missing required 'type'"):
        _parse("""
record:
  name: Thing
  fields:
    - name: broken_field
""")


def test_unknown_type_raises():
    with pytest.raises(SchemaParseError, match="unknown type"):
        _parse("""
record:
  name: Thing
  fields:
    - name: f
      type: not_a_real_type
""")


def test_enum_without_values_raises():
    with pytest.raises(SchemaParseError, match="must define 'values'"):
        _parse("""
record:
  name: Thing
  fields:
    - name: status
      type: enum
""")


def test_array_without_items_raises():
    with pytest.raises(SchemaParseError, match="must define 'items'"):
        _parse("""
record:
  name: Thing
  fields:
    - name: tags
      type: array
""")


def test_defaults_to_required_true():
    schema = _parse("""
record:
  name: Thing
  fields:
    - name: f
      type: string
""")
    assert schema.root.fields[0].required is True


def test_explicit_required_false_respected():
    schema = _parse("""
record:
  name: Thing
  fields:
    - name: f
      type: string
      required: false
""")
    assert schema.root.fields[0].required is False


def test_nested_array_of_records_preserves_inner_record_name():
    schema = _parse("""
record:
  name: Outer
  fields:
    - name: children
      type: array
      items:
        type: record
        name: Child
        fields:
          - name: id
            type: string
""")
    item_field = schema.root.fields[0].item
    assert item_field.kind == FieldKind.RECORD
    assert item_field.record.name == "Child"


def test_field_level_inline_record_keeps_field_name_separate_from_type_name():
    """Regression test: a field named 'user' of type record with
    record_name 'UserRef' must keep field.name == 'user', not have it
    clobbered by the nested record's type name. This was a real bug
    where both used the same 'name' YAML key."""
    schema = _parse("""
record:
  name: Outer
  fields:
    - name: user
      type: record
      record_name: UserRef
      fields:
        - name: user_id
          type: string
""")
    field = schema.root.fields[0]
    assert field.name == "user"
    assert field.record.name == "UserRef"


def test_field_level_inline_record_without_explicit_record_name_uses_pascal_case_default():
    schema = _parse("""
record:
  name: Outer
  fields:
    - name: shipping_address
      type: record
      fields:
        - name: city
          type: string
""")
    field = schema.root.fields[0]
    assert field.name == "shipping_address"
    assert field.record.name == "ShippingAddress"


def test_default_namespace_and_version_applied():
    schema = _parse("""
record:
  name: Thing
  fields: []
""")
    assert schema.namespace == "schemalattice.generated"
    assert schema.version == "1.0.0"


def test_field_default_value_carried_through():
    schema = _parse("""
record:
  name: Thing
  fields:
    - name: qty
      type: int
      default: 1
""")
    f = schema.root.fields[0]
    assert f.has_default is True
    assert f.default == 1
