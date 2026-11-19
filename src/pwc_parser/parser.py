"""Parse PowerCenter XML into a navigable model using only the standard library."""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

from .model import Connection, Definition, Field, Instance, Mapping, PowerCenterDocument


def _tag(element: ET.Element) -> str:
    """Return a namespace-independent, uppercase element name."""
    return element.tag.rsplit("}", 1)[-1].upper()


def _attrs(element: ET.Element) -> dict[str, str]:
    return {key.upper(): value for key, value in element.attrib.items()}


def _definition(element: ET.Element, kind: str, field_tag: str) -> Definition:
    attributes = _attrs(element)
    fields = tuple(
        Field(name=_attrs(child).get("NAME", ""), attributes=_attrs(child))
        for child in element if _tag(child) == field_tag
    )
    return Definition(kind=kind, name=attributes.get("NAME", ""), attributes=attributes, fields=fields)


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

    return PowerCenterDocument(
        attributes=_attrs(root), repositories=tuple(repositories), folders=tuple(folders),
        sources=tuple(sources), targets=tuple(targets), mappings=tuple(mappings),
    )


def _parse_mapping(element: ET.Element) -> Mapping:
    attributes = _attrs(element)
    transformations = tuple(
        _definition(child, "TRANSFORMATION", "TRANSFORMFIELD")
        for child in element if _tag(child) == "TRANSFORMATION"
    )
    instances: list[Instance] = []
    connections: list[Connection] = []
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
    return Mapping(
        name=attributes.get("NAME", ""), attributes=attributes,
        transformations=transformations, instances=tuple(instances), connections=tuple(connections),
    )
