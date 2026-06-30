# schemalattice
.
Define a data schema once, in a single readable YAML file, and generate
**JSON Schema**, **Protobuf**, and **Avro** from it — instead of hand
authoring and manually keeping three schema files in sync.

```
                     ┌──────────────────┐
                     │   order.sl.yaml  │   <- single source of truth
                     └────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
      JSON Schema         Protobuf           Avro
      (REST APIs,        (gRPC, internal    (Kafka, data
       OpenAPI)            services)         lake / Spark)
```

## Why this exists

Teams running Kafka (Avro) + gRPC (Protobuf) + a public REST API (JSON
Schema) commonly end up maintaining three separate schema files by hand
for the same logical data shape. They drift. A field gets renamed in the
Protobuf definition during a refactor and nobody updates the Avro schema
that the analytics pipeline depends on, and you find out in production.

schemalattice doesn't try to be a lossless bidirectional translator
between all three formats — that's a much harder, more ambitious problem
(see [`docs/design-notes.md`](docs/design-notes.md) for why we
deliberately scoped *away* from that). It solves the narrower, very
common case: you're defining a new data shape, you want it expressed
once, and you want correct, idiomatic output in three different target
formats — plus tooling to keep it that way as the schema evolves.

## Features

- **One schema, three targets** — a single `.sl.yaml` file generates a
  JSON Schema (draft 2020-12) document, a `.proto` (proto3) file, and an
  `.avsc` Avro schema.
- **`schemalattice lint`** — catches duplicate field names, reserved
  words that would break generated code, malformed identifiers, and
  enum problems before you generate anything.
- **`schemalattice validate`** — validate a real JSON data file against
  your schema from the command line.
- **`schemalattice diff`** — compare two versions of a schema and get a
  per-target compatibility report (Avro / Protobuf / JSON Schema each
  have *different* rules for what counts as a breaking change — see
  below). This is the feature most projects in this space don't have,
  because most schema tools target a single format and don't need to
  think about a change being safe in Protobuf but breaking in Avro.
- Supports nested records, arrays, maps, enums, optional fields with
  defaults, and doc comments that propagate into all three outputs.

## Installation

```bash
pip install schemalattice
```

Or from source:

```bash
git clone https://github.com/schemalattice/schemalattice.git
cd schemalattice
pip install -e ".[dev]"
```

## Quick start

```yaml
# order.sl.yaml
namespace: com.example.orders
version: "1.0.0"
record:
  name: Order
  doc: "A single customer order"
  fields:
    - name: order_id
      type: string
      required: true
    - name: total_cents
      type: long
      required: true
    - name: status
      type: enum
      values: [PENDING, PAID, SHIPPED, CANCELLED]
    - name: items
      type: array
      items:
        type: record
        name: OrderItem
        fields:
          - name: sku
            type: string
          - name: qty
            type: int
            default: 1
```

```bash
# Generate all three targets into ./out/
schemalattice generate order.sl.yaml -o out/

# Or just one
schemalattice generate order.sl.yaml --target proto

# Lint before you generate
schemalattice lint order.sl.yaml

# Validate a sample payload against the schema
schemalattice validate order.sl.yaml sample_order.json

# Check what changed between two versions, and whether it's safe
schemalattice diff order_v1.sl.yaml order_v2.sl.yaml
```

## Schema DSL reference

See [`docs/schema-dsl.md`](docs/schema-dsl.md) for the full field
reference (every supported type, `required`, `default`, nested
`record`/`array`/`map`, and the `record_name` field used to disambiguate
a field's own name from its nested record type's name).

Worked examples of increasing complexity live in
[`examples/`](examples/), including a deliberately deep one
([`examples/user_activity_event.sl.yaml`](examples/user_activity_event.sl.yaml))
with records nested inside arrays nested inside records.

## On compatibility checking

Avro, Protobuf, and JSON Schema do not agree on what makes a schema
change "safe":

| Change                              | Avro       | Protobuf (proto3) | JSON Schema |
|--------------------------------------|------------|--------------------|-------------|
| Add optional field                   | safe       | safe                | safe        |
| Add required field, no default       | **breaking** | safe              | **breaking** |
| Add required field, with default     | safe       | safe                | safe (n/a — JSON Schema has no field-level default enforcement at read time) |
| Remove a field                        | **breaking** (for old readers) | safe (ignored) | depends on required-ness |
| Add an enum value                     | safe       | safe                | **breaking** (closed-world `enum` validation) |
| Reorder fields                        | safe       | **breaking*** | safe |

\* schemalattice assigns Protobuf field numbers from declaration order
(see [`docs/design-notes.md`](docs/design-notes.md#field-numbering)), so
reordering fields in the `.sl.yaml` file silently renumbers every
Protobuf field after the moved one. `schemalattice diff` specifically
flags this, because it's the easiest mistake to make and the hardest one
to notice — there's no error, just silently wrong data on the wire.

Run `schemalattice diff old.sl.yaml new.sl.yaml --fail-on-breaking` in CI
to catch breaking changes before merge.

## Project status

This is an actively developed, pre-1.0 project. The core generation
pipeline (parser → IR → three generators) is stable and covered by tests
that validate generated output against each format's real reference
library (`jsonschema`, `fastavro`, and `protoc` itself — see
[`tests/test_roundtrip.py`](tests/test_roundtrip.py)), not just "does it
produce text that looks right."

See [`ROADMAP.md`](ROADMAP.md) for planned work and
[`CONTRIBUTING.md`](CONTRIBUTING.md) to get involved.

## License

Apache 2.0 — see [`LICENSE`](LICENSE).
