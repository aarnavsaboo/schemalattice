import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemalattice.compat import ChangeKind, Impact, diff_schemas, has_breaking_changes
from schemalattice.parser import parse_schema_dict


def _schema(yaml_text: str):
    return parse_schema_dict(yaml.safe_load(yaml_text))


def test_identical_schemas_have_no_diff():
    s = _schema("""
record:
  name: Thing
  fields:
    - name: id
      type: string
""")
    assert diff_schemas(s, s) == []


def test_adding_optional_field_is_safe_everywhere():
    old = _schema("""
record:
  name: Thing
  fields:
    - name: id
      type: string
""")
    new = _schema("""
record:
  name: Thing
  fields:
    - name: id
      type: string
    - name: nickname
      type: string
      required: false
""")
    changes = diff_schemas(old, new)
    assert len(changes) == 1
    assert changes[0].kind == ChangeKind.FIELD_ADDED
    assert all(v == Impact.SAFE for v in changes[0].impact_by_target.values())
    assert not has_breaking_changes(changes)


def test_adding_required_field_without_default_breaks_avro_and_json_schema():
    old = _schema("""
record:
  name: Thing
  fields:
    - name: id
      type: string
""")
    new = _schema("""
record:
  name: Thing
  fields:
    - name: id
      type: string
    - name: email
      type: string
      required: true
""")
    changes = diff_schemas(old, new)
    field_added = changes[0]
    assert field_added.impact_by_target["avro"] == Impact.BREAKING
    assert field_added.impact_by_target["json_schema"] == Impact.BREAKING
    assert field_added.impact_by_target["protobuf"] == Impact.SAFE
    assert has_breaking_changes(changes)
    assert not has_breaking_changes(changes, targets=["protobuf"])


def test_adding_required_field_with_default_is_avro_safe():
    old = _schema("""
record:
  name: Thing
  fields:
    - name: id
      type: string
""")
    new = _schema("""
record:
  name: Thing
  fields:
    - name: id
      type: string
    - name: retries
      type: int
      required: true
      default: 0
""")
    changes = diff_schemas(old, new)
    field_added = changes[0]
    assert field_added.impact_by_target["avro"] == Impact.SAFE


def test_removing_field_is_breaking():
    old = _schema("""
record:
  name: Thing
  fields:
    - name: id
      type: string
    - name: legacy_field
      type: string
""")
    new = _schema("""
record:
  name: Thing
  fields:
    - name: id
      type: string
""")
    changes = diff_schemas(old, new)
    assert any(c.kind == ChangeKind.FIELD_REMOVED for c in changes)
    assert has_breaking_changes(changes)


def test_field_reorder_without_add_or_remove_flags_protobuf_breaking():
    old = _schema("""
record:
  name: Thing
  fields:
    - name: a
      type: string
    - name: b
      type: string
""")
    new = _schema("""
record:
  name: Thing
  fields:
    - name: b
      type: string
    - name: a
      type: string
""")
    changes = diff_schemas(old, new)
    reorder = [c for c in changes if c.kind == ChangeKind.FIELD_REORDERED]
    assert len(reorder) == 1
    assert reorder[0].impact_by_target["protobuf"] == Impact.BREAKING
    assert reorder[0].impact_by_target["avro"] == Impact.SAFE


def test_enum_value_removed_is_breaking_for_all_targets():
    old = _schema("""
record:
  name: Thing
  fields:
    - name: status
      type: enum
      values: [A, B, C]
""")
    new = _schema("""
record:
  name: Thing
  fields:
    - name: status
      type: enum
      values: [A, B]
""")
    changes = diff_schemas(old, new)
    removed = [c for c in changes if c.kind == ChangeKind.ENUM_VALUE_REMOVED]
    assert len(removed) == 1
    assert all(v == Impact.BREAKING for v in removed[0].impact_by_target.values())


def test_enum_value_added_breaks_json_schema_closed_world_validation():
    old = _schema("""
record:
  name: Thing
  fields:
    - name: status
      type: enum
      values: [A, B]
""")
    new = _schema("""
record:
  name: Thing
  fields:
    - name: status
      type: enum
      values: [A, B, C]
""")
    changes = diff_schemas(old, new)
    added = [c for c in changes if c.kind == ChangeKind.ENUM_VALUE_ADDED]
    assert added[0].impact_by_target["json_schema"] == Impact.BREAKING
    assert added[0].impact_by_target["avro"] == Impact.SAFE


def test_type_change_is_universally_breaking():
    old = _schema("""
record:
  name: Thing
  fields:
    - name: id
      type: string
""")
    new = _schema("""
record:
  name: Thing
  fields:
    - name: id
      type: int
""")
    changes = diff_schemas(old, new)
    assert changes[0].kind == ChangeKind.FIELD_TYPE_CHANGED
    assert all(v == Impact.BREAKING for v in changes[0].impact_by_target.values())


def test_nested_record_changes_are_detected():
    old = _schema("""
record:
  name: Outer
  fields:
    - name: inner
      type: record
      record_name: Inner
      fields:
        - name: id
          type: string
""")
    new = _schema("""
record:
  name: Outer
  fields:
    - name: inner
      type: record
      record_name: Inner
      fields:
        - name: id
          type: string
        - name: extra
          type: string
          required: true
""")
    changes = diff_schemas(old, new)
    assert any("Outer.inner.extra" in c.path for c in changes)
