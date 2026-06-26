"""
Compatibility checker: compares two versions of a schema and classifies
every change as BREAKING, SAFE, or INFO.

This matters because the whole point of having one schema generate
Avro/Protobuf/JSON Schema simultaneously is that those three formats have
*different* compatibility rules:

- Avro: adding a field is safe ONLY if it has a default. Removing a
  required field is always breaking for old readers.
- Protobuf (proto3): adding a field is always safe (unknown fields are
  ignored on read). Renumbering or reusing a field number is catastrophic
  — it silently corrupts data rather than erroring.
- JSON Schema: adding a required field is breaking for existing producers
  who don't yet send it. Adding an optional field is always safe.

Because schemalattice generates field numbers deterministically from
declaration order (see generators/protobuf_gen.py), the single most
dangerous operation in this whole system is *reordering or deleting* a
field in the middle of a record — that silently shifts every subsequent
proto field number, which downstream consumers will read as the wrong
field entirely with no error at all. This checker exists specifically to
catch that class of mistake before it ships.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .ir import Field, FieldKind, RecordType, Schema


class ChangeKind(Enum):
    FIELD_ADDED = "field_added"
    FIELD_REMOVED = "field_removed"
    FIELD_TYPE_CHANGED = "field_type_changed"
    FIELD_BECAME_REQUIRED = "field_became_required"
    FIELD_BECAME_OPTIONAL = "field_became_optional"
    FIELD_REORDERED = "field_reordered"
    ENUM_VALUE_ADDED = "enum_value_added"
    ENUM_VALUE_REMOVED = "enum_value_removed"
    DEFAULT_ADDED = "default_added"
    DEFAULT_REMOVED = "default_removed"


class Impact(Enum):
    BREAKING = "breaking"
    SAFE = "safe"
    INFO = "info"


@dataclass
class Change:
    kind: ChangeKind
    path: str
    impact_by_target: dict  # {"avro": Impact, "protobuf": Impact, "json_schema": Impact}
    detail: str

    def __str__(self) -> str:
        impacts = ", ".join(f"{t}={i.value}" for t, i in self.impact_by_target.items())
        return f"{self.kind.value} @ {self.path} ({impacts}): {self.detail}"


def diff_schemas(old: Schema, new: Schema) -> list[Change]:
    changes: list[Change] = []
    _diff_records(old.root, new.root, path=old.root.name, changes=changes)
    return changes


def _diff_records(old: RecordType, new: RecordType, path: str, changes: list[Change]) -> None:
    old_fields_by_name = {f.name: f for f in old.fields}
    new_fields_by_name = {f.name: f for f in new.fields}
    old_order = [f.name for f in old.fields]
    new_order = [f.name for f in new.fields]

    for name, old_field in old_fields_by_name.items():
        field_path = f"{path}.{name}"
        if name not in new_fields_by_name:
            changes.append(Change(
                kind=ChangeKind.FIELD_REMOVED,
                path=field_path,
                impact_by_target={
                    "avro": Impact.BREAKING,
                    "protobuf": Impact.SAFE if not old_field.required else Impact.BREAKING,
                    "json_schema": Impact.BREAKING if old_field.required else Impact.SAFE,
                },
                detail="field removed — old readers/writers expecting this field will break "
                       "unless every target's default/optionality rules tolerate absence",
            ))
            continue

        new_field = new_fields_by_name[name]
        _diff_field(old_field, new_field, field_path, changes)

    for name, new_field in new_fields_by_name.items():
        if name not in old_fields_by_name:
            field_path = f"{path}.{name}"
            avro_safe = (not new_field.required) or new_field.has_default
            changes.append(Change(
                kind=ChangeKind.FIELD_ADDED,
                path=field_path,
                impact_by_target={
                    "avro": Impact.SAFE if avro_safe else Impact.BREAKING,
                    "protobuf": Impact.SAFE,
                    "json_schema": Impact.SAFE if not new_field.required else Impact.BREAKING,
                },
                detail="new field added" + (
                    "" if avro_safe else " — Avro requires a default value "
                    "for new fields to remain backward-compatible"
                ),
            ))

    # Field reordering is uniquely dangerous for protobuf because field
    # numbers are derived from declaration order in this tool (see module
    # docstring) — catch it even when no fields were added/removed.
    common = [n for n in old_order if n in new_fields_by_name]
    common_new_order = [n for n in new_order if n in old_fields_by_name]
    if common != common_new_order:
        changes.append(Change(
            kind=ChangeKind.FIELD_REORDERED,
            path=path,
            impact_by_target={
                "avro": Impact.SAFE,
                "protobuf": Impact.BREAKING,
                "json_schema": Impact.SAFE,
            },
            detail=f"field declaration order changed ({common} -> {common_new_order}); "
                   f"since schemalattice assigns protobuf field numbers by position, "
                   f"this silently shifts every field number after the reordered fields",
        ))


def _diff_field(old_field: Field, new_field: Field, path: str, changes: list[Change]) -> None:
    if old_field.kind != new_field.kind:
        changes.append(Change(
            kind=ChangeKind.FIELD_TYPE_CHANGED,
            path=path,
            impact_by_target={
                "avro": Impact.BREAKING, "protobuf": Impact.BREAKING, "json_schema": Impact.BREAKING,
            },
            detail=f"type changed from {old_field.kind.value} to {new_field.kind.value}",
        ))
        return  # don't bother diffing further sub-structure of a type that changed entirely

    if old_field.required and not new_field.required:
        changes.append(Change(
            kind=ChangeKind.FIELD_BECAME_OPTIONAL,
            path=path,
            impact_by_target={"avro": Impact.SAFE, "protobuf": Impact.SAFE, "json_schema": Impact.SAFE},
            detail="field changed from required to optional",
        ))
    elif not old_field.required and new_field.required:
        changes.append(Change(
            kind=ChangeKind.FIELD_BECAME_REQUIRED,
            path=path,
            impact_by_target={"avro": Impact.BREAKING, "protobuf": Impact.SAFE, "json_schema": Impact.BREAKING},
            detail="field changed from optional to required — old producers that omit "
                   "this field will now fail validation/parsing",
        ))

    if old_field.has_default and not new_field.has_default:
        changes.append(Change(
            kind=ChangeKind.DEFAULT_REMOVED,
            path=path,
            impact_by_target={"avro": Impact.BREAKING, "protobuf": Impact.INFO, "json_schema": Impact.INFO},
            detail="default value removed",
        ))
    elif not old_field.has_default and new_field.has_default:
        changes.append(Change(
            kind=ChangeKind.DEFAULT_ADDED,
            path=path,
            impact_by_target={"avro": Impact.SAFE, "protobuf": Impact.INFO, "json_schema": Impact.INFO},
            detail="default value added",
        ))

    if old_field.kind == FieldKind.ENUM:
        old_values = set(old_field.enum.values)
        new_values = set(new_field.enum.values)
        for removed in old_values - new_values:
            changes.append(Change(
                kind=ChangeKind.ENUM_VALUE_REMOVED,
                path=path,
                impact_by_target={"avro": Impact.BREAKING, "protobuf": Impact.BREAKING, "json_schema": Impact.BREAKING},
                detail=f"enum value '{removed}' removed — readers expecting it will error",
            ))
        for added in new_values - old_values:
            changes.append(Change(
                kind=ChangeKind.ENUM_VALUE_ADDED,
                path=path,
                impact_by_target={"avro": Impact.SAFE, "protobuf": Impact.SAFE, "json_schema": Impact.BREAKING},
                detail=f"enum value '{added}' added — note JSON Schema enum validation "
                       f"is closed-world, so old consumers validating against the old "
                       f"schema will reject this new value",
            ))

    if old_field.kind == FieldKind.RECORD:
        _diff_records(old_field.record, new_field.record, path, changes)

    if old_field.kind in (FieldKind.ARRAY, FieldKind.MAP) and old_field.item.kind == FieldKind.RECORD:
        if new_field.item.kind == FieldKind.RECORD:
            _diff_records(old_field.item.record, new_field.item.record, f"{path}[]", changes)


def has_breaking_changes(changes: list[Change], targets: list[str] | None = None) -> bool:
    targets = targets or ["avro", "protobuf", "json_schema"]
    return any(
        c.impact_by_target.get(t) == Impact.BREAKING
        for c in changes
        for t in targets
    )


def format_changes(changes: list[Change]) -> str:
    if not changes:
        return "no changes detected"
    return "\n".join(str(c) for c in changes)
