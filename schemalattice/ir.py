"""
Intermediate representation (IR) for schemalattice.

This is the single source-of-truth data model that the parser builds from
a .sl.yaml file, and that every generator (JSON Schema / Protobuf / Avro)
consumes. Keeping this layer dumb and format-agnostic is what lets the
three generators stay independent of each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class FieldKind(Enum):
    STRING = "string"
    INT = "int"
    LONG = "long"
    FLOAT = "float"
    DOUBLE = "double"
    BOOL = "bool"
    BYTES = "bytes"
    TIMESTAMP = "timestamp"  # logical type, maps to format/logicalType per target
    ENUM = "enum"
    RECORD = "record"
    ARRAY = "array"
    MAP = "map"


PRIMITIVE_KINDS = {
    FieldKind.STRING,
    FieldKind.INT,
    FieldKind.LONG,
    FieldKind.FLOAT,
    FieldKind.DOUBLE,
    FieldKind.BOOL,
    FieldKind.BYTES,
    FieldKind.TIMESTAMP,
}


@dataclass
class EnumType:
    name: str
    values: list[str]
    doc: Optional[str] = None


@dataclass
class Field:
    name: str
    kind: FieldKind
    doc: Optional[str] = None
    required: bool = True
    default: object = None
    has_default: bool = False

    # Used when kind == RECORD
    record: Optional["RecordType"] = None
    # Used when kind == ENUM
    enum: Optional[EnumType] = None
    # Used when kind == ARRAY or MAP: the element type (recursive Field with no name)
    item: Optional["Field"] = None
    # Used when kind == MAP: key type is always assumed string (true for JSON/Avro/Proto map<string,V>)


@dataclass
class RecordType:
    name: str
    fields: list[Field] = field(default_factory=list)
    doc: Optional[str] = None
    namespace: Optional[str] = None


@dataclass
class Schema:
    """Top level container. A schema file may define one root record plus
    any number of nested records/enums, but generators only need the root —
    nested types are reachable via Field.record / Field.enum."""
    root: RecordType
    namespace: str = "schemalattice.generated"
    version: str = "1.0.0"
