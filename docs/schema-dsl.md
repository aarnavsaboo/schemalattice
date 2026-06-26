# Schema DSL reference

A schema file (conventionally named `*.sl.yaml`) has three top-level
keys:

```yaml
namespace: com.example.orders   # optional, default: "schemalattice.generated"
version: "1.0.0"                # optional, default: "1.0.0"
record:                         # required — the root record type
  name: Order
  fields: [...]
```

## Record

```yaml
record:
  name: Order            # required
  doc: "..."              # optional doc comment, propagated to all 3 targets
  fields:                 # list of field definitions, see below
    - ...
```

## Fields

Every field has at minimum a `name` and a `type`:

```yaml
- name: order_id
  type: string
```

Common optional keys on any field:

| Key         | Default | Meaning |
|-------------|---------|---------|
| `doc`       | none    | Doc comment, included in all 3 outputs |
| `required`  | `true`  | Whether the field must be present |
| `default`   | none    | Default value (see per-type notes below) |

### Primitive types

`string`, `int`, `long`, `float`, `double`, `bool`, `bytes`, `timestamp`

```yaml
- name: total_cents
  type: long
- name: is_active
  type: bool
  default: true
```

See [`docs/design-notes.md`](design-notes.md#timestamps) for how
`timestamp` maps across targets — it's the one type whose wire
representation genuinely differs between JSON Schema, Avro, and
Protobuf, so it's worth understanding before you rely on it across a
pipeline that uses more than one target.

### Enum

```yaml
- name: status
  type: enum
  values: [PENDING, PAID, SHIPPED, CANCELLED]
```

The generated enum type name defaults to `<FieldName>Enum` (PascalCase).
Protobuf enums always get a generated `_UNSPECIFIED = 0` zero value
prepended, since proto3 requires the first enum value to be zero — this
follows the standard proto3 enum convention and isn't something you need
to declare yourself.

### Record (nested)

```yaml
- name: user
  type: record
  record_name: UserRef    # the nested record TYPE's name — see note below
  fields:
    - name: user_id
      type: string
```

**Important:** `record_name` is required to differ from the field's own
`name` when you want the generated type to have a specific name. If you
omit `record_name`, it defaults to a PascalCase version of the field
name (`shipping_address` → `ShippingAddress`). See
[`docs/design-notes.md`](design-notes.md#why-record_name-exists-as-a-separate-key-from-name)
for why this is a separate key rather than reusing `name`.

### Array

```yaml
- name: items
  type: array
  items:
    type: record       # the item can be any type, including primitive
    name: OrderItem     # for array items, 'name' IS the type name (no ambiguity here)
    fields:
      - name: sku
        type: string
```

Arrays of primitives work the same way without `fields`:

```yaml
- name: tags
  type: array
  items:
    type: string
```

### Map

Maps always have string keys (matching what JSON Schema, Avro, and
Protobuf all support natively as `map<string, V>` / `additionalProperties`
/ Avro `map`). Specify the value type under `values`:

```yaml
- name: metadata
  type: map
  values:
    type: string
```

## Full example

See [`examples/user_activity_event.sl.yaml`](../examples/user_activity_event.sl.yaml)
for a schema exercising every feature at once: nested records inside a
record, arrays of records, records nested inside arrays nested inside
records, maps, enums with defaults, and a mix of required/optional
fields throughout.
