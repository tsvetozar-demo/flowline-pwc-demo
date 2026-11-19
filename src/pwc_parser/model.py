"""Typed, lightweight representation of PowerCenter repository XML."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator


@dataclass(frozen=True)
class Field:
    name: str
    attributes: dict[str, str] = field(default_factory=dict)

    @property
    def expression(self) -> str | None:
        return self.attributes.get("EXPRESSION")


@dataclass(frozen=True)
class Definition:
    kind: str
    name: str
    attributes: dict[str, str] = field(default_factory=dict)
    fields: tuple[Field, ...] = ()


@dataclass(frozen=True)
class Instance:
    name: str
    definition_name: str
    definition_type: str
    instance_type: str
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Connection:
    from_instance: str
    from_field: str
    to_instance: str
    to_field: str
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Mapping:
    name: str
    attributes: dict[str, str] = field(default_factory=dict)
    transformations: tuple[Definition, ...] = ()
    instances: tuple[Instance, ...] = ()
    connections: tuple[Connection, ...] = ()

    def find_instance(self, name: str) -> Instance | None:
        """Look up a mapping instance by its mapping-local name."""
        return next((instance for instance in self.instances if instance.name == name), None)

    def find_transformation(self, name: str) -> Definition | None:
        """Look up a transformation definition by its definition name."""
        return next((item for item in self.transformations if item.name == name), None)

    def iter_transformations(self, kind: str | None = None) -> Iterator[Definition]:
        """Yield transformation definitions, optionally filtered by type."""
        for transformation in self.transformations:
            if kind is None or transformation.attributes.get("TYPE", "").casefold() == kind.casefold():
                yield transformation

    def iter_instances(self, instance_type: str | None = None) -> Iterator[Instance]:
        for instance in self.instances:
            if instance_type is None or instance.instance_type.casefold() == instance_type.casefold():
                yield instance

    def iter_connections_from(self, instance: str, field_name: str | None = None) -> Iterator[Connection]:
        for connection in self.connections:
            if connection.from_instance == instance and (field_name is None or connection.from_field == field_name):
                yield connection

    def iter_connections_to(self, instance: str, field_name: str | None = None) -> Iterator[Connection]:
        for connection in self.connections:
            if connection.to_instance == instance and (field_name is None or connection.to_field == field_name):
                yield connection


@dataclass(frozen=True)
class PowerCenterDocument:
    attributes: dict[str, str] = field(default_factory=dict)
    repositories: tuple[Definition, ...] = ()
    folders: tuple[Definition, ...] = ()
    sources: tuple[Definition, ...] = ()
    targets: tuple[Definition, ...] = ()
    mappings: tuple[Mapping, ...] = ()

    def iter_mappings(self) -> Iterator[Mapping]:
        return iter(self.mappings)

    def iter_definitions(self, kind: str | None = None) -> Iterator[Definition]:
        groups = (self.repositories, self.folders, self.sources, self.targets)
        for group in groups:
            for definition in group:
                if kind is None or definition.kind.casefold() == kind.casefold():
                    yield definition

    def find_mapping(self, name: str) -> Mapping | None:
        return next((mapping for mapping in self.mappings if mapping.name == name), None)
