"""Resolve the parsed PowerCenter model into mapping transformation graphs."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .model import Definition, Mapping, PowerCenterDocument


def _definition_dict(definition: Definition) -> dict[str, Any]:
    """Make a definition useful to consumers without exposing XML elements."""
    attributes = dict(definition.attributes)
    attributes.update(definition.properties)
    return {
        "name": definition.name,
        "kind": definition.kind,
        "attributes": attributes,
        "ports": {field.name: dict(field.attributes) for field in definition.fields},
    }


def _definitions(document: PowerCenterDocument | None, kind: str) -> dict[str, Definition]:
    if document is None:
        return {}
    return {item.name: item for item in document.iter_definitions(kind)}


def build_mapping_graph(
    mapping: Mapping,
    document: PowerCenterDocument | None = None,
) -> dict[str, object]:
    """Build a single global structure for one mapping.

    Transformation definitions are keyed by definition name, while instances,
    sources, and targets are keyed by their mapping-local instance name. This
    distinction matters because PowerCenter permits one definition to have
    multiple instances.
    """
    sources = _definitions(document, "SOURCE")
    targets = _definitions(document, "TARGET")
    source_instances: dict[str, dict[str, Any]] = {}
    target_instances: dict[str, dict[str, Any]] = {}
    instances: dict[str, dict[str, Any]] = {}

    for instance in mapping.instances:
        value = dict(instance.attributes)
        value.update({
            "name": instance.name,
            "definition_name": instance.definition_name,
            "definition_type": instance.definition_type,
            "instance_type": instance.instance_type,
        })
        instances[instance.name] = value
        instance_type = instance.instance_type.casefold()
        definition = sources.get(instance.definition_name) if "source" in instance_type else None
        if definition is not None:
            source_instances[instance.name] = _definition_dict(definition)
        definition = targets.get(instance.definition_name) if "target" in instance_type else None
        if definition is not None:
            target_instances[instance.name] = _definition_dict(definition)

    return {
        "name": mapping.name,
        "transformations": {
            definition.name: {
                "type": definition.attributes.get("TYPE", ""),
                "ports": {field.name: dict(field.attributes) for field in definition.fields},
                "attributes": {**definition.attributes, **definition.properties},
            }
            for definition in mapping.transformations
        },
        "instances": instances,
        "connectors": [asdict(connection) for connection in mapping.connections],
        "sources": source_instances,
        "targets": target_instances,
        "attributes": dict(mapping.attributes),
        "variables": dict(mapping.variables),
    }


def build_project_definition(document: PowerCenterDocument) -> dict[str, object]:
    """Build the project-level configuration containing every mapping graph."""
    from .workflow import build_workflow_definition

    return {
        "mappings": {
            mapping.name: build_mapping_graph(mapping, document)
            for mapping in document.mappings
        },
        "workflows": {
            workflow.name: build_workflow_definition(workflow, document)
            for workflow in document.workflows
        },
    }
