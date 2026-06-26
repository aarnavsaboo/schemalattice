"""
Linter for schemalattice schema definitions.

Catches mistakes that would otherwise surface as confusing errors deep
inside one specific generator (e.g. a duplicate field name producing a
broken .proto, or a Python/Java reserved word silently producing
uncompileable generated code). Centralizing these checks means every
target benefits, and the error messages can point back at the actual
problem in the .sl.yaml file instead of a stack trace from protoc.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .ir import Field, FieldKind, RecordType, Schema

# Reserved words across the languages most commonly generated from these
# schemas (Python, Java, Go, C++) — used as a field-name lint, since a
# field called e.g. "class" or "import" will break codegen for at least
# one target even though it's perfectly valid YAML.
_RESERVED_WORDS = {
    "class", "import", "def", "return", "yield", "lambda", "global",
    "package", "interface", "extends", "implements", "static", "final",
    "public", "private", "protected", "namespace", "template", "typename",
    "message", "enum", "service", "rpc", "syntax", "option", "repeated",
    "optional", "required", "true", "false", "null", "void", "new",
    "delete", "this", "self", "type",
}

# Protobuf field numbers 19000-19999 are reserved by the protobuf runtime.
_PROTO_RESERVED_RANGE = range(19000, 20000)


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class LintIssue:
    severity: Severity
    message: str
    path: str  # dotted path to the offending field/record, e.g. "Order.items.sku"

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.path}: {self.message}"


def lint(schema: Schema) -> list[LintIssue]:
    issues: list[LintIssue] = []
    _lint_record(schema.root, path=schema.root.name, issues=issues, seen_enum_names={})
    return issues


def _lint_record(record: RecordType, path: str, issues: list[LintIssue], seen_enum_names: dict) -> None:
    seen_field_names: set[str] = set()

    for f in record.fields:
        field_path = f"{path}.{f.name}"

        if f.name in seen_field_names:
            issues.append(LintIssue(
                Severity.ERROR,
                f"duplicate field name '{f.name}' in record '{record.name}'",
                field_path,
            ))
        seen_field_names.add(f.name)

        if f.name.lower() in _RESERVED_WORDS:
            issues.append(LintIssue(
                Severity.WARNING,
                f"field name '{f.name}' is a reserved word in one or more "
                f"target languages (Python/Java/Go/C++/protobuf) and may "
                f"produce uncompileable generated code",
                field_path,
            ))

        if not f.name.replace("_", "").isalnum():
            issues.append(LintIssue(
                Severity.ERROR,
                f"field name '{f.name}' contains characters other than "
                f"letters, digits, and underscores, which is invalid in "
                f"Protobuf and most generated-code targets",
                field_path,
            ))

        if f.name and f.name[0].isdigit():
            issues.append(LintIssue(
                Severity.ERROR,
                f"field name '{f.name}' starts with a digit, which is "
                f"invalid in Protobuf, Avro, and most languages",
                field_path,
            ))

        if f.kind == FieldKind.ENUM:
            existing = seen_enum_names.get(f.enum.name)
            if existing and existing != tuple(f.enum.values):
                issues.append(LintIssue(
                    Severity.ERROR,
                    f"enum type '{f.enum.name}' is defined more than once "
                    f"with different value sets — this will silently "
                    f"collide in Avro/Protobuf namespaces",
                    field_path,
                ))
            seen_enum_names[f.enum.name] = tuple(f.enum.values)

            if len(f.enum.values) == 0:
                issues.append(LintIssue(
                    Severity.ERROR, "enum has no values defined", field_path,
                ))
            if len(set(f.enum.values)) != len(f.enum.values):
                issues.append(LintIssue(
                    Severity.ERROR, "enum has duplicate values", field_path,
                ))

        if f.kind == FieldKind.RECORD:
            _lint_record(f.record, path=field_path, issues=issues, seen_enum_names=seen_enum_names)

        if f.kind in (FieldKind.ARRAY, FieldKind.MAP) and f.item.kind == FieldKind.RECORD:
            _lint_record(f.item.record, path=f"{field_path}[]", issues=issues, seen_enum_names=seen_enum_names)

    if len(record.fields) == 0:
        issues.append(LintIssue(
            Severity.WARNING, f"record '{record.name}' has no fields defined", path,
        ))


def format_issues(issues: list[LintIssue]) -> str:
    if not issues:
        return "no issues found"
    return "\n".join(str(i) for i in issues)


def has_errors(issues: list[LintIssue]) -> bool:
    return any(i.severity == Severity.ERROR for i in issues)
