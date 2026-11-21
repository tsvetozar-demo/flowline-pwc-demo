#!/usr/bin/env python3
"""Inspect PowerCenter mappings and generate dbt model SQL."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


# Allow ``python cmd/pwc_to_dbt.py ...`` from a source checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pwc_parser import (  # noqa: E402
    build_project_definition,
    generate_dbt_models,
    generate_model_sql,
    generate_workflow_models,
    parse_file,
    build_workflow_definition,
)


def _document(path: str):
    return parse_file(path)


def inventory(args: argparse.Namespace) -> int:
    document = _document(args.xml)
    for mapping in document.mappings:
        print(
            f"{mapping.name}: "
            f"{len(mapping.transformations)} transformations, "
            f"{len(mapping.instances)} instances, "
            f"{len(mapping.connections)} connectors"
        )
    return 0


def graph(args: argparse.Namespace) -> int:
    document = _document(args.xml)
    project = build_project_definition(document)
    mappings = project["mappings"]
    if args.mapping:
        mappings = {args.mapping: mappings[args.mapping]}
    for name, mapping in mappings.items():
        print(f"[{name}]")
        print(f"transformations: {len(mapping['transformations'])}")
        print(f"instances: {len(mapping['instances'])}")
        print(f"connectors: {len(mapping['connectors'])}")
        print(f"sources: {', '.join(mapping['sources']) or '(none)'}")
        print(f"targets: {', '.join(mapping['targets']) or '(none)'}")
    return 0


def generate(args: argparse.Namespace) -> int:
    document = _document(args.xml)
    paths = generate_dbt_models(document, args.output, source_name=args.source_name)
    for path in paths:
        print(path)
    print(f"Generated {len(paths)} model(s) in {args.output}")
    return 0


def model(args: argparse.Namespace) -> int:
    document = _document(args.xml)
    mapping = document.find_mapping(args.mapping)
    if mapping is None:
        raise ValueError(f"Unknown mapping: {args.mapping}")
    print(generate_model_sql(mapping, document, args.target, source_name=args.source_name))
    return 0


def workflow(args: argparse.Namespace) -> int:
    document = _document(args.xml)
    selected = document.find_workflow(args.workflow)
    if selected is None:
        raise ValueError(f"Unknown workflow: {args.workflow}")
    definition = build_workflow_definition(selected, document)
    print(f"[{definition['name']}]")
    for item in definition["execution_plan"]:
        print(f"{item['session']} -> {item['mapping']}")
    if args.output:
        paths = generate_workflow_models(document, selected, args.output, args.source_name)
        print(f"Generated {len(paths)} model(s) in {args.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pwc_to_dbt", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory_parser = subparsers.add_parser("inventory", help="list mappings and their sizes")
    inventory_parser.add_argument("xml", help="PowerCenter XML export")
    inventory_parser.set_defaults(function=inventory)

    graph_parser = subparsers.add_parser("graph", help="inspect mapping graph sizes")
    graph_parser.add_argument("xml", help="PowerCenter XML export")
    graph_parser.add_argument("--mapping", help="show only one mapping")
    graph_parser.set_defaults(function=graph)

    generate_parser = subparsers.add_parser("generate", help="write dbt SQL model files")
    generate_parser.add_argument("xml", help="PowerCenter XML export")
    generate_parser.add_argument("-o", "--output", default="models/staging", help="output directory")
    generate_parser.add_argument("--source-name", default="raw", help="dbt source name")
    generate_parser.set_defaults(function=generate)

    model_parser = subparsers.add_parser("model", help="print one generated dbt model")
    model_parser.add_argument("xml", help="PowerCenter XML export")
    model_parser.add_argument("mapping", help="mapping name")
    model_parser.add_argument("target", help="target instance name")
    model_parser.add_argument("--source-name", default="raw", help="dbt source name")
    model_parser.set_defaults(function=model)

    workflow_parser = subparsers.add_parser("workflow", help="inspect or execute workflow sessions")
    workflow_parser.add_argument("xml", help="PowerCenter XML export")
    workflow_parser.add_argument("workflow", help="workflow name")
    workflow_parser.add_argument("-o", "--output", default="models/staging", help="generate models in this directory")
    workflow_parser.add_argument("--source-name", default="raw", help="dbt source name")
    workflow_parser.set_defaults(function=workflow)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.function(args)
    except (KeyError, ValueError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
