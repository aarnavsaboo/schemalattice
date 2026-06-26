# Design notes

This document explains the non-obvious decisions in schemalattice and
why they were made. It exists because several of these decisions are
easy to second-guess without the context of what they trade off against.

## Why one-way generation, not bidirectional translation

It's tempting to want schemalattice to also *ingest* an existing
Protobuf or Avro schema and emit the unified DSL, so teams with existing
schemas could adopt the tool without a rewrite. We deliberately scoped
this out of v0.1.

The three formats are not isomorphic. Avro's union types, Protobuf's
`oneof`, and JSON Schema's `anyOf`/`oneOf` overlap but don't map 1:1.
Protobuf has no native concept of a default-less required field in
proto3; Avro has no concept of Protobuf's field numbers; JSON Schema has
no binary encoding at all. A genuinely faithful bidirectional translator
needs to either (a) support only the intersection of features all three
formats agree on, which would make the DSL nearly useless for anything
beyond flat records, or (b) carry lossy, format-specific metadata through
an intermediate representation that wasn't designed for it, which is how
"unified schema language" projects historically turn into unmaintainable
messes. (Worth reading: most engineers who deeply understand all three
formats have considered building this and decided not to — see the
"second system trap" discussion that's fairly well known in this space.)

One-way generation (DSL → all three) avoids this entirely: the DSL only
needs to support what schemalattice itself defines, and each generator
only needs to map *that* into its target, which is a much smaller and
more tractable problem.

## Field numbering (Protobuf)

Protobuf field numbers are currently assigned sequentially from
declaration order in the `.sl.yaml` file, starting at 1. This is the
right default for a schema being authored fresh, but it has a sharp
edge: **reordering or removing a field in the YAML silently renumbers
every field declared after it.** Protobuf doesn't error on this — old
binary-encoded data will simply be decoded against the wrong field
numbers, producing wrong values with no exception thrown anywhere.

`schemalattice diff` (see `compat.py`) specifically detects field
reordering and flags it as Protobuf-breaking, specifically because this
failure mode produces no error message anywhere in the stack — it just
quietly corrupts data. This is the single most important thing the diff
tool exists to catch.

The longer-term fix (tracked in `ROADMAP.md`) is to support **pinned
field numbers**: an explicit `proto_number:` key on a field that, once
set, is never recomputed even if the field's position in the YAML
changes. This is the same approach real Protobuf schemas use once they
reach production (reserving field numbers, never reusing them). It's not
implemented yet because it adds real complexity (you need to track
"never reuse this number even after the field is deleted") that didn't
seem worth the cost until the rest of the pipeline was solid.

## Why Avro optional fields are unions with null, not implicit

JSON Schema lets you simply omit a key from `required` to make a field
optional — there's no wrapper type involved. Avro has no equivalent
concept; the *only* way to express "this field might be absent" in Avro
is a union type `["null", T]` with a default of `null`. We follow Avro's
own convention here rather than inventing something cleverer, because
every Avro consumer (fastavro, the Java Avro library, Confluent's tools)
expects this exact shape. Fighting that convention to make Avro "feel
more like JSON Schema" would produce schemas that don't interoperate
with the rest of the Avro ecosystofem.

## Why `record_name` exists as a separate key from `name`

Early versions of the DSL used a single `name:` key for both "this
field's name in the parent record" and "this nested record type's name"
when a field's type was `record`. That's how most people's first
instinct writes a nested-record field:

```yaml
- name: user
  type: record
  fields: [...]
```

The bug this caused: a field named `user` containing a record that
should be typed `UserRef` has nowhere to put `UserRef` without
overloading the same `name:` key — and if you do overload it (writing
`name: UserRef` instead of `name: user`), you silently lose the field's
actual name and every generator emits `UserRef` as both the field name
*and* the type name (e.g. Protobuf emits `UserRef UserRef = 4;` instead
of `UserRef user = 4;`).

The fix was a separate `record_name:` key, with a sensible PascalCase
default derived from the field name if you don't specify one (`user` →
`User`) — see `parser/__init__.py::_default_record_type_name`. Array and
map items don't have this ambiguity (there's no separate field name to
collide with), so `name:` is allowed to double as the type name in that
context — see `_parse_inline_record`'s `allow_name_as_type` parameter.
This asymmetry looks inconsistent at a glance but each branch is correct
for its own context; `tests/test_parser.py` has regression tests for
both.

## Timestamps

`type: timestamp` maps to:
- JSON Schema: `{"type": "string", "format": "date-time"}` (ISO 8601)
- Avro: `{"type": "long", "logicalType": "timestamp-millis"}` (epoch
  milliseconds)
- Protobuf: `int64` (epoch milliseconds, by convention — we don't pull
  in `google.protobuf.Timestamp` from the well-known-types import to
  avoid forcing an extra dependency on every generated `.proto`, but
  this is a real tradeoff and is called out explicitly in a comment in
  the generated file)

These three representations are *not* the same bytes-on-the-wire, which
matters if you're serializing the same logical timestamp value across
all three systems in the same pipeline — you need to convert at the
boundary either way, since none of these formats share a wire
representation for time regardless of what tool generated the schema.
