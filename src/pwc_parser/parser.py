"""Parse PowerCenter XML into a navigable model using only the standard library."""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

from .model import (
    Connection, Definition, Field, Instance, Mapping, PowerCenterDocument,
    Session, Workflow, WorkflowLink, WorkflowTask,
)


def _tag(element: ET.Element) -> str:
    """Return a namespace-independent, uppercase element name."""
    return element.tag.rsplit("}", 1)[-1].upper()


def _attrs(element: ET.Element) -> dict[str, str]:
    return {key.upper(): value for key, value in element.attrib.items()}


def _definition(element: ET.Element, kind: str, field_tag: str) -> Definition:
    attributes = _attrs(element)
    properties = {
        _attrs(child).get("NAME", ""): _attrs(child).get("VALUE", "")
        for child in element if _tag(child) == "TABLEATTRIBUTE" and _attrs(child).get("NAME")
    }
    fields = tuple(
        Field(name=_attrs(child).get("NAME", ""), attributes=_attrs(child))
        for child in element if _tag(child) == field_tag
    )
    return Definition(
        kind=kind, name=attributes.get("NAME", ""), attributes=attributes,
        fields=fields, properties=properties,
    )


def parse_file(path: str | Path) -> PowerCenterDocument:
    """Parse an XML file path (including PowerCenter Windows-1252 exports)."""
    return _parse_root(ET.parse(path).getroot())


def parse_string(xml_text: str | bytes) -> PowerCenterDocument:
    """Parse XML text or bytes into a PowerCenterDocument."""
    return _parse_root(ET.fromstring(xml_text))


def _parse_root(root: ET.Element) -> PowerCenterDocument:
    repositories: list[Definition] = []
    folders: list[Definition] = []
    sources: list[Definition] = []
    targets: list[Definition] = []
    mappings: list[Mapping] = []
    sessions: list[Session] = []
    workflows: list[Workflow] = []

    for repository in (node for node in root.iter() if _tag(node) == "REPOSITORY"):
        repositories.append(_definition(repository, "REPOSITORY", ""))
    for folder in (node for node in root.iter() if _tag(node) == "FOLDER"):
        folders.append(_definition(folder, "FOLDER", ""))
        for child in folder:
            tag = _tag(child)
            if tag == "SOURCE":
                sources.append(_definition(child, "SOURCE", "SOURCEFIELD"))
            elif tag == "TARGET":
                targets.append(_definition(child, "TARGET", "TARGETFIELD"))
            elif tag == "MAPPING":
                mappings.append(_parse_mapping(child))
            elif tag == "WORKFLOW":
                workflows.append(_parse_workflow(child))
        # Reusable sessions live beside mappings; non-reusable sessions can be
        # nested inside a workflow. Both are session definitions.
        for node in folder.iter():
            if _tag(node) == "SESSION":
                sessions.append(_parse_session(node))

    return PowerCenterDocument(
        attributes=_attrs(root), repositories=tuple(repositories), folders=tuple(folders),
        sources=tuple(sources), targets=tuple(targets), mappings=tuple(mappings),
        sessions=tuple(sessions), workflows=tuple(workflows),
    )


def _parse_session(element: ET.Element) -> Session:
    attributes = _attrs(element)
    return Session(
        name=attributes.get("NAME", ""),
        mapping_name=attributes.get("MAPPINGNAME", ""),
        reusable=attributes.get("REUSABLE", "").casefold() == "yes",
        attributes=attributes,
    )


def _parse_workflow(element: ET.Element) -> Workflow:
    tasks: list[WorkflowTask] = []
    links: list[WorkflowLink] = []
    for child in element:
        tag = _tag(child)
        attributes = _attrs(child)
        if tag == "TASKINSTANCE":
            tasks.append(WorkflowTask(
                name=attributes.get("NAME", ""),
                task_name=attributes.get("TASKNAME", ""),
                task_type=attributes.get("TASKTYPE", ""),
                attributes=attributes,
            ))
        elif tag == "WORKFLOWLINK":
            links.append(WorkflowLink(
                from_task=attributes.get("FROMTASK", ""),
                to_task=attributes.get("TOTASK", ""),
                condition=attributes.get("CONDITION", ""),
                attributes=attributes,
            ))
    return Workflow(
        name=_attrs(element).get("NAME", ""),
        attributes=_attrs(element),
        tasks=tuple(tasks),
        links=tuple(links),
    )


def _parse_mapping(element: ET.Element) -> Mapping:
    attributes = _attrs(element)
    transformations = tuple(
        _definition(child, "TRANSFORMATION", "TRANSFORMFIELD")
        for child in element if _tag(child) == "TRANSFORMATION"
    )
    instances: list[Instance] = []
    connections: list[Connection] = []
    variables: dict[str, str] = {}
    for child in element:
        tag = _tag(child)
        item = _attrs(child)
        if tag == "INSTANCE":
            instances.append(Instance(
                name=item.get("NAME", ""),
                definition_name=item.get("TRANSFORMATION_NAME", ""),
                definition_type=item.get("TRANSFORMATION_TYPE", ""),
                instance_type=item.get("TYPE", ""),
                attributes=item,
            ))
        elif tag == "CONNECTOR":
            connections.append(Connection(
                from_instance=item.get("FROMINSTANCE", ""),
                from_field=item.get("FROMFIELD", ""),
                to_instance=item.get("TOINSTANCE", ""),
                to_field=item.get("TOFIELD", ""),
                attributes=item,
            ))
        elif tag in {"VARIABLE", "MAPPINGVARIABLE"}:
            if item.get("NAME"):
                variables[item["NAME"]] = item.get("VALUE", item.get("DEFAULTVALUE", ""))
    return Mapping(
        name=attributes.get("NAME", ""), attributes=attributes,
        transformations=transformations, instances=tuple(instances), connections=tuple(connections),
        variables=variables,
    )
