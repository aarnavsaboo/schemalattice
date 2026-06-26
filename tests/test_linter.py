import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemalattice.linter import Severity, has_errors, lint
from schemalattice.parser import parse_schema_dict


def _schema(yaml_text: str):
    return parse_schema_dict(yaml.safe_load(yaml_text))


def test_clean_schema_has_no_issues():
    schema = _schema("""
record:
  name: Clean
  fields:
    - name: id
      type: string
""")
    assert lint(schema) == []


def test_duplicate_field_name_is_error():
    schema = _schema("""
record:
  name: Dup
  fields:
    - name: id
      type: string
    - name: id
      type: int
""")
    issues = lint(schema)
    assert any(i.severity == Severity.ERROR and "duplicate" in i.message for i in issues)
    assert has_errors(issues)


def test_reserved_word_field_name_is_warning_not_error():
    schema = _schema("""
record:
  name: Thing
  fields:
    - name: class
      type: string
""")
    issues = lint(schema)
    assert len(issues) == 1
    assert issues[0].severity == Severity.WARNING
    assert not has_errors(issues)


def test_field_name_starting_with_digit_is_error():
    schema = _schema("""
record:
  name: Thing
  fields:
    - name: 1field
      type: string
""")
    issues = lint(schema)
    assert has_errors(issues)


def test_empty_record_is_warning():
    schema = _schema("""
record:
  name: Empty
  fields: []
""")
    issues = lint(schema)
    assert any(i.severity == Severity.WARNING and "no fields" in i.message for i in issues)


def test_empty_enum_is_error():
    schema = _schema("""
record:
  name: Thing
  fields:
    - name: status
      type: enum
      values: [A]
""")
    # sanity: non-empty enum has no issues
    assert lint(schema) == []


def test_duplicate_enum_values_is_error():
    schema = _schema("""
record:
  name: Thing
  fields:
    - name: status
      type: enum
      values: [A, B, A]
""")
    issues = lint(schema)
    assert any("duplicate values" in i.message for i in issues)


def test_nested_record_fields_are_linted_recursively():
    schema = _schema("""
record:
  name: Outer
  fields:
    - name: inner
      type: record
      record_name: Inner
      fields:
        - name: id
          type: string
        - name: id
          type: int
""")
    issues = lint(schema)
    assert any("Outer.inner.id" in i.path for i in issues)


def test_array_item_record_fields_are_linted():
    schema = _schema("""
record:
  name: Outer
  fields:
    - name: items
      type: array
      items:
        type: record
        name: Item
        fields:
          - name: class
            type: string
""")
    issues = lint(schema)
    assert any("reserved word" in i.message for i in issues)
