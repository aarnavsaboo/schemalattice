"""
Round-trip correctness tests.

The point of these tests is NOT "does the generator produce text that
looks like the target format" — it's "does the generated schema actually
accept valid data and reject invalid data, when checked by that format's
own real-world library."

- JSON Schema -> validated with `jsonschema` (the reference Python impl)
- Avro        -> validated with `fastavro` (used in production by many
                 real Kafka/data-pipeline shops)
- Protobuf    -> validated by actually invoking `protoc` to compile the
                 generated .proto and checking it doesn't error
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import fastavro
import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemalattice.generators import avro_gen, json_schema_gen, protobuf_gen
from schemalattice.parser import parse_schema_file

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "order.sl.yaml"

VALID_ORDER = {
    "order_id": "ord_123",
    "total_cents": 4599,
    "status": "PAID",
    "placed_at": "2026-06-27T10:00:00Z",
    "items": [
        {"sku": "SKU-1", "qty": 2, "unit_price_cents": 1500},
        {"sku": "SKU-2", "qty": 1, "unit_price_cents": 1599},
    ],
    "metadata": {"channel": "web"},
}

INVALID_ORDER_MISSING_REQUIRED = {
    "order_id": "ord_124",
    # missing total_cents, status, placed_at, items
}

INVALID_ORDER_BAD_ENUM = {
    "order_id": "ord_125",
    "total_cents": 100,
    "status": "NOT_A_REAL_STATUS",
    "placed_at": "2026-06-27T10:00:00Z",
    "items": [],
}


@pytest.fixture(scope="module")
def schema():
    return parse_schema_file(str(EXAMPLE))


class TestJsonSchema:
    def test_valid_data_passes(self, schema):
        js = json_schema_gen.generate(schema)
        jsonschema.validate(VALID_ORDER, js)  # raises if invalid

    def test_missing_required_field_fails(self, schema):
        js = json_schema_gen.generate(schema)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(INVALID_ORDER_MISSING_REQUIRED, js)

    def test_bad_enum_value_fails(self, schema):
        js = json_schema_gen.generate(schema)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(INVALID_ORDER_BAD_ENUM, js)

    def test_optional_field_can_be_omitted(self, schema):
        js = json_schema_gen.generate(schema)
        data = dict(VALID_ORDER)
        del data["metadata"]  # metadata is required: false
        jsonschema.validate(data, js)


class TestAvro:
    def test_valid_data_round_trips(self, schema):
        avsc = avro_gen.generate(schema)
        parsed = fastavro.parse_schema(avsc)

        # Avro requires the optional `notes` field to be present (as None)
        # since it's a union type with no implicit omission like JSON.
        data = dict(VALID_ORDER)
        data["notes"] = None
        data["placed_at"] = 1782900000000  # epoch-millis, as Avro timestamp-millis requires

        with tempfile.NamedTemporaryFile(suffix=".avro") as tmp:
            with open(tmp.name, "wb") as out:
                fastavro.writer(out, parsed, [data])
            with open(tmp.name, "rb") as src:
                records = list(fastavro.reader(src))

        assert len(records) == 1
        assert records[0]["order_id"] == "ord_123"
        assert records[0]["status"] == "PAID"
        assert records[0]["items"][0]["sku"] == "SKU-1"

    def test_bad_enum_value_rejected_by_avro(self, schema):
        avsc = avro_gen.generate(schema)
        parsed = fastavro.parse_schema(avsc)
        data = dict(VALID_ORDER)
        data["notes"] = None
        data["placed_at"] = 1782900000000
        data["status"] = "NOT_A_REAL_STATUS"

        with pytest.raises(ValueError):
            with tempfile.NamedTemporaryFile(suffix=".avro") as tmp:
                with open(tmp.name, "wb") as out:
                    fastavro.writer(out, parsed, [data])


class TestProtobuf:
    def test_generated_proto_compiles(self, schema):
        proto_text = protobuf_gen.generate(schema)

        with tempfile.TemporaryDirectory() as td:
            proto_path = Path(td) / "order.proto"
            proto_path.write_text(proto_text)

            protoc = _find_protoc()
            if protoc:
                result = subprocess.run(
                    [protoc, f"--proto_path={td}", f"--python_out={td}", str(proto_path)],
                    capture_output=True, text=True,
                )
                ok, stderr = result.returncode == 0, result.stderr
            else:
                # Fall back to grpc_tools' bundled protoc, invoked in-process.
                from grpc_tools import protoc as grpc_protoc
                rc = grpc_protoc.main([
                    "protoc", f"--proto_path={td}", f"--python_out={td}", str(proto_path),
                ])
                ok, stderr = rc == 0, f"grpc_tools.protoc exited with code {rc}"

            assert ok, f"protoc failed to compile generated .proto:\n{stderr}"
            # Confirm the compiler actually emitted a usable Python module.
            generated = list(Path(td).glob("*_pb2.py"))
            assert generated, "protoc did not emit a _pb2.py file"

    def test_field_numbers_are_unique_and_sequential(self, schema):
        proto_text = protobuf_gen.generate(schema)
        order_block = proto_text.split("message Order {")[1].split("}")[0]
        numbers = []
        for line in order_block.splitlines():
            line = line.strip()
            if "=" in line and ";" in line:
                num = int(line.split("=")[1].split(";")[0].strip())
                numbers.append(num)
        assert numbers == sorted(numbers)
        assert len(numbers) == len(set(numbers))


def _find_protoc():
    import shutil
    return shutil.which("protoc")
