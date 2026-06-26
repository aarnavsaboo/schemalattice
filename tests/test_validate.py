import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemalattice.parser import parse_schema_dict
from schemalattice.validate import validate_data


def _schema(yaml_text: str):
    return parse_schema_dict(yaml.safe_load(yaml_text))


SIMPLE_SCHEMA = _schema("""
record:
  name: Person
  fields:
    - name: name
      type: string
      required: true
    - name: age
      type: int
      required: true
    - name: nickname
      type: string
      required: false
""")


def test_valid_data_passes():
    result = validate_data(SIMPLE_SCHEMA, {"name": "Aarav", "age": 25})
    assert result.valid
    assert result.errors == []


def test_missing_required_field_fails_with_clear_message():
    result = validate_data(SIMPLE_SCHEMA, {"name": "Aarav"})
    assert not result.valid
    assert any("age" in e for e in result.errors)


def test_wrong_type_fails():
    result = validate_data(SIMPLE_SCHEMA, {"name": "Aarav", "age": "twenty-five"})
    assert not result.valid


def test_extra_unknown_field_fails_due_to_additional_properties_false():
    result = validate_data(SIMPLE_SCHEMA, {"name": "Aarav", "age": 25, "ssn": "123-45-6789"})
    assert not result.valid


def test_optional_field_can_be_omitted():
    result = validate_data(SIMPLE_SCHEMA, {"name": "Aarav", "age": 25})
    assert result.valid


def test_optional_field_can_be_provided():
    result = validate_data(SIMPLE_SCHEMA, {"name": "Aarav", "age": 25, "nickname": "AC"})
    assert result.valid


def test_result_is_truthy_falsy_based_on_validity():
    valid_result = validate_data(SIMPLE_SCHEMA, {"name": "Aarav", "age": 25})
    invalid_result = validate_data(SIMPLE_SCHEMA, {})
    assert bool(valid_result) is True
    assert bool(invalid_result) is False
