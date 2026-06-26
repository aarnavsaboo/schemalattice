# Roadmap

This is a living list of planned work, roughly ordered by priority.
"Planned" doesn't mean committed to a date — this is a side project
maintained as time allows. PRs against any of these are very welcome;
see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Near term

- **Pinned Protobuf field numbers.** Currently field numbers are derived
  from declaration order (see `docs/design-notes.md#field-numbering`),
  which is fragile across schema edits. Add an optional `proto_number:`
  key on fields that, once set, is never recomputed — and track
  "retired" numbers from deleted fields so they're never silently
  reused.
- **`oneOf` / union support.** Right now a field has exactly one type.
  Real-world schemas frequently need "this field is either an `A` or a
  `B`" (Avro unions, Protobuf `oneof`, JSON Schema `oneOf` all support
  this natively already — the DSL doesn't expose it yet).
- **`$import` for multi-file schemas.** Large schemas currently have to
  live in one `.sl.yaml` file. Support referencing a record defined in
  another file, so e.g. a shared `Address` record can be defined once
  and reused across multiple top-level schemas.
- **Decimal / fixed-precision numeric type.** Avro's `decimal` logical
  type and Protobuf's common "scaled integer" convention for money
  aren't currently representable — right now you have to fall back to
  `long` (minor units) as a workaround, as the example schemas do for
  currency fields.

## Medium term

- **GraphQL as a fourth target.** Several people who've looked at this
  project have asked for GraphQL SDL generation. It's a reasonable fit
  for the existing IR (object types, enums, lists all map cleanly) —
  the main open question is how to handle GraphQL's lack of a `map`
  type.
- **`schemalattice init`** — scaffold a new schema file interactively
  (or from a `--from-json-sample data.json` flag that infers a starting
  schema from example data, similar to what quicktype does for code
  generation).
- **Compatibility mode presets** for `schemalattice diff` — right now
  every change is reported with its full per-target impact, but most
  teams only care about one or two targets. A `--profile kafka-only` or
  similar would streamline the output for the common case.

## Long term / exploratory

- **Schema registry integration.** Optionally push generated Avro/JSON
  Schema directly to a Confluent-compatible schema registry as part of
  `generate`, with the registry's own compatibility check as a second
  opinion alongside schemalattice's own `diff` command.
- **Language-specific codegen on top of the generated schemas** (e.g.
  Python dataclasses or TypeScript types derived from the JSON Schema
  output) — explicitly out of scope for schemalattice itself, but
  documented here because it's the most common follow-up question, and
  the honest answer is "use `datamodel-code-generator` or `quicktype` on
  the JSON Schema output we already produce" rather than reinventing
  that wheel inside this project.

## Explicitly not planned

- **Bidirectional translation** (ingesting existing Avro/Protobuf and
  emitting the unified DSL). See
  `docs/design-notes.md#why-one-way-generation-not-bidirectional-translation`
  for the reasoning — this would either restrict the DSL to the lowest
  common denominator of all three formats, or require lossy
  format-specific escape hatches that undermine the whole point of a
  unified schema.
