# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- Field-level inline records (`type: record` directly on a field, e.g.
  a field named `user` typed as `UserRef`) were silently losing their
  own field name to the nested record's type name when both were
  written under the same `name:` YAML key. A field named `user`
  containing a `UserRef` record would generate `UserRef UserRef = N;`
  in Protobuf instead of `UserRef user = N;`, and the equivalent
  collision in JSON Schema and Avro output. Fixed by introducing a
  separate `record_name:` key for the nested type's name. See
  `docs/design-notes.md` for the full explanation and
  `tests/test_parser.py::test_field_level_inline_record_keeps_field_name_separate_from_type_name`
  for the regression test.

## [0.1.0] - 2026-06-27

### Added
- Core IR (`ir.py`) and YAML-based DSL parser (`parser/`) supporting
  primitives, enums, nested records, arrays, and maps, with
  required/optional fields and default values.
- Three generators: JSON Schema (draft 2020-12), Protobuf (proto3), and
  Avro.
- `schemalattice generate` CLI command with single-target or
  generate-all modes.
- `schemalattice lint` — catches duplicate field names, reserved-word
  field names, malformed identifiers, and enum issues before
  generation.
- `schemalattice validate` — validates a JSON data file against a
  schema using the generated JSON Schema + the `jsonschema` library.
- `schemalattice diff` — compares two schema versions and reports a
  per-target (Avro / Protobuf / JSON Schema) breaking-vs-safe
  classification for every change, including the Protobuf-specific
  field-reordering hazard described in `docs/design-notes.md`.
- Round-trip test suite that validates generated schemas against real
  target libraries (`jsonschema`, `fastavro`, and an actual `protoc`
  compile via `grpcio-tools`), not just structural inspection of the
  generated text.
- Two worked example schemas (`examples/order.sl.yaml`,
  `examples/user_activity_event.sl.yaml`) and three schema-evolution
  examples under `examples/evolution/` demonstrating safe vs. breaking
  changes for the `diff` command.
- Full documentation set: `README.md`, `docs/schema-dsl.md` (DSL
  reference), `docs/design-notes.md` (architectural rationale),
  `ROADMAP.md`, `CONTRIBUTING.md`.
