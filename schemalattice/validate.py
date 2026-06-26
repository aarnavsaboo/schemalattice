"""
Validates a JSON data file against a schemalattice schema, using the
JSON Schema generator + the real `jsonschema` library as the runtime
check. This is the fastest of the three targets to validate against
since it doesn't require a binary serialization round-trip, which makes
it the natural choice for a "does my sample data match the schema"
CLI command.
"""

from __future__ import annotations

import json

import jsonschema

from .generators import json_schema_gen
from .ir import Schema


class ValidationResult:
    def __init__(self, valid: bool, errors: list[str]):
        self.valid = valid
        self.errors = errors

    def __bool__(self) -> bool:
        return self.valid


def validate_data(schema: Schema, data: dict) -> ValidationResult:
    json_schema = json_schema_gen.generate(schema)
    validator_cls = jsonschema.validators.validator_for(json_schema)
    validator = validator_cls(json_schema)

    errors = []
    for err in validator.iter_errors(data):
        loc = ".".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"{loc}: {err.message}")

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def validate_data_file(schema: Schema, data_file_path: str) -> ValidationResult:
    with open(data_file_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return validate_data(schema, data)
