# Contributing to schemalattice

Thanks for considering contributing! This is a young project, so the
process is intentionally lightweight.

## Getting set up

```bash
git clone https://github.com/schemalattice/schemalattice.git
cd schemalattice
pip install -e ".[dev]"
pytest
```

All 47+ tests should pass before you start. If `tests/test_roundtrip.py`'s
Protobuf compilation test skips rather than passing, you're missing a
protoc-equivalent compiler — install `grpcio-tools` (`pip install
grpcio-tools`) or a standalone `protoc` binary and re-run.

## Before opening a PR

1. **Add a test.** Every generator bug fixed in this project so far was
   caught by a round-trip test that actually validates generated output
   against the real target library (`jsonschema`, `fastavro`, `protoc`)
   — not by inspecting that the output "looks right." If you're fixing
   a generator bug, the test should fail before your fix and pass after.
2. **Run `pytest` and `schemalattice lint` against the example schemas**
   in `examples/` to make sure nothing regressed.
3. **Update `docs/schema-dsl.md`** if you're adding or changing DSL
   syntax — the docs and the parser drift apart fast otherwise.
4. **Add an entry to `CHANGELOG.md`** under `[Unreleased]`.

## What kinds of contributions are most useful right now

Check [`ROADMAP.md`](ROADMAP.md) first — pinned Protobuf field numbers
and `oneOf`/union support are the two most-requested gaps right now and
both are scoped clearly enough to pick up without much back-and-forth.

Bug reports with a minimal reproducing `.sl.yaml` snippet are extremely
valuable even if you don't have time to fix them yourself — the
`record_name` vs `name` disambiguation bug documented in
`docs/design-notes.md` is exactly the kind of subtle issue that's easy
to hit and easy to fix once it's clearly reproduced.

## Code style

- Type hints on function signatures, no exceptions.
- Each generator (`generators/*.py`) should stay independent — no
  generator should import from another generator. Shared logic belongs
  in `ir.py` or a new shared module, not duplicated or cross-imported.
- Prefer raising `SchemaParseError` with a specific, actionable message
  over a bare `KeyError`/`TypeError` bubbling up from deep in the parser
  — see the existing error messages in `parser/__init__.py` for the
  tone we're going for (state what's wrong and which field).

## Reporting security issues

This project generates schemas, not security-sensitive infrastructure,
but if you find an issue where a maliciously crafted `.sl.yaml` file
could cause something worse than a parse error (e.g. arbitrary file
write outside the intended output directory), please open an issue
tagged `security` rather than a public PR with a working exploit.
