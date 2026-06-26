"""
Command-line interface for schemalattice.

Subcommands:
    schemalattice generate  --target <fmt> schema.sl.yaml
    schemalattice lint       schema.sl.yaml
    schemalattice validate   schema.sl.yaml data.json
    schemalattice diff       old_schema.sl.yaml new_schema.sl.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from . import compat, linter
from .generators import avro_gen, json_schema_gen, protobuf_gen
from .parser import SchemaParseError, parse_schema_file
from .validate import validate_data_file

_TARGETS = {
    "json-schema": ("json", lambda s: json.dumps(json_schema_gen.generate(s), indent=2)),
    "avro": ("avsc", lambda s: json.dumps(avro_gen.generate(s), indent=2)),
    "proto": ("proto", lambda s: protobuf_gen.generate(s)),
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="schemalattice")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate one or more schema targets from a .sl.yaml file")
    gen.add_argument("schema_file")
    gen.add_argument("--target", "-t", choices=list(_TARGETS.keys()) + ["all"], default="all")
    gen.add_argument("--output", "-o", default=None)
    gen.add_argument("--no-lint", action="store_true", help="Skip linting before generation")

    lint_cmd = sub.add_parser("lint", help="Check a schema for common mistakes")
    lint_cmd.add_argument("schema_file")
    lint_cmd.add_argument("--strict", action="store_true", help="Treat warnings as errors (exit 1)")

    validate_cmd = sub.add_parser("validate", help="Validate a JSON data file against a schema")
    validate_cmd.add_argument("schema_file")
    validate_cmd.add_argument("data_file")

    diff_cmd = sub.add_parser("diff", help="Compare two schema versions and report compatibility impact")
    diff_cmd.add_argument("old_schema_file")
    diff_cmd.add_argument("new_schema_file")
    diff_cmd.add_argument(
        "--fail-on-breaking", action="store_true",
        help="Exit with code 1 if any breaking change is detected for any target",
    )

    args = parser.parse_args(argv)

    if args.command == "generate":
        return _run_generate(args)
    if args.command == "lint":
        return _run_lint(args)
    if args.command == "validate":
        return _run_validate(args)
    if args.command == "diff":
        return _run_diff(args)
    return 1


def _load_schema_or_exit(path: str):
    try:
        return parse_schema_file(path)
    except (SchemaParseError, yaml.YAMLError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def _run_generate(args) -> int:
    schema = _load_schema_or_exit(args.schema_file)

    if not args.no_lint:
        issues = linter.lint(schema)
        if issues:
            print(linter.format_issues(issues), file=sys.stderr)
        if linter.has_errors(issues):
            print("error: lint errors found, aborting generation (use --no-lint to override)", file=sys.stderr)
            return 1

    targets = list(_TARGETS.keys()) if args.target == "all" else [args.target]

    if len(targets) == 1 and args.output and not Path(args.output).is_dir():
        ext, fn = _TARGETS[targets[0]]
        out_path = Path(args.output)
        out_path.write_text(fn(schema))
        print(f"wrote {out_path}")
        return 0

    if len(targets) == 1 and not args.output:
        _, fn = _TARGETS[targets[0]]
        print(fn(schema))
        return 0

    out_dir = Path(args.output) if args.output else Path(".")
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = schema.root.name.lower()
    for target in targets:
        ext, fn = _TARGETS[target]
        out_path = out_dir / f"{base_name}.{ext}"
        out_path.write_text(fn(schema))
        print(f"wrote {out_path}")
    return 0


def _run_lint(args) -> int:
    schema = _load_schema_or_exit(args.schema_file)
    issues = linter.lint(schema)
    print(linter.format_issues(issues))
    if linter.has_errors(issues):
        return 1
    if args.strict and issues:
        return 1
    return 0


def _run_validate(args) -> int:
    schema = _load_schema_or_exit(args.schema_file)
    try:
        result = validate_data_file(schema, args.data_file)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if result.valid:
        print(f"{args.data_file}: valid")
        return 0
    print(f"{args.data_file}: INVALID", file=sys.stderr)
    for err in result.errors:
        print(f"  - {err}", file=sys.stderr)
    return 1


def _run_diff(args) -> int:
    old_schema = _load_schema_or_exit(args.old_schema_file)
    new_schema = _load_schema_or_exit(args.new_schema_file)
    changes = compat.diff_schemas(old_schema, new_schema)
    print(compat.format_changes(changes))

    if args.fail_on_breaking and compat.has_breaking_changes(changes):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
