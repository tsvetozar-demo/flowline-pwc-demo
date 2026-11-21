"""Generate dbt model SQL from a parsed PowerCenter mapping graph.

This is deliberately an intermediate SQL generator: it preserves the graph's
lineage and expressions and provides conservative fallbacks for transformation
types that need additional dialect-specific handling.
"""

from __future__ import annotations

from pathlib import Path
import re
from .model import Definition, Instance, Mapping, PowerCenterDocument, Workflow
from .workflow import workflow_execution_plan
from .validation import validate_or_raise


def translate_expression(expression: str | None) -> str:
    """Translate the small set of common Informatica functions used in SQL."""
    if not expression:
        return ""
    result = expression.strip()
    result = re.sub(r"\bTRUNC\s*\(([^()]+)\)", r"DATE_TRUNC('day', \1)", result, flags=re.IGNORECASE)
    result = re.sub(
        r"TO_DATE\s*\(\s*TO_CHAR\s*\(([^,]+),\s*'[^']+'\)\s*,\s*'[^']+'\s*\)",
        r"CAST(\1 AS DATE)", result, flags=re.IGNORECASE,
    )
    return result


def _sql_name(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_").lower()
    return value or "model"


def _relation_ref_name(instance: Instance) -> str:
    """Resolve every PowerCenter input to a dbt-managed ``ref`` node."""
    return _sql_name(instance.definition_name)


class DbtModelGenerator:
    """Generate one dbt model per target instance in a mapping."""

    def __init__(
        self,
        mapping: Mapping,
        document: PowerCenterDocument,
        source_name: str = "raw",
    ) -> None:
        self.mapping = mapping
        self.document = document
        self.source_name = source_name
        self._definitions = {item.name: item for item in mapping.transformations}
        self._instances = {item.name: item for item in mapping.instances}
        self._ctes: dict[str, str] = {}
        self._building: set[str] = set()

    def target_instances(self) -> tuple[Instance, ...]:
        return tuple(item for item in self.mapping.instances if "target" in item.instance_type.casefold())

    def render_target(self, target: Instance) -> str:
        incoming = tuple(self.mapping.iter_connections_to(target.name))
        if not incoming:
            raise ValueError(f"Target instance {target.name!r} has no incoming connector")
        source_instance = self._instances[incoming[0].from_instance]
        relation = self._render_instance(source_instance)
        columns = ",\n".join(
            f"    {self._column_expression(connection.from_field, relation)} AS {connection.to_field}"
            for connection in incoming
        )
        ctes = ",\n\n".join(self._ctes.values())
        prefix = f"WITH\n{ctes}\n\n" if ctes else ""
        return f"{prefix}SELECT\n{columns}\nFROM {relation}\n"

    def _column_expression(self, field: str, relation: str) -> str:
        return f"{relation}.{field}"

    @staticmethod
    def _qualify_expression(expression: str, incoming_by_field: dict[str, tuple[str, str]]) -> str:
        """Qualify known input port names while leaving literals and functions intact."""
        result = expression
        names = sorted({name for name, (_, source_field) in incoming_by_field.items()} |
                       {source_field for _, source_field in incoming_by_field.values()}, key=len, reverse=True)
        for name in names:
            alias = incoming_by_field.get(name, (None, name))[0]
            if alias:
                result = re.sub(rf"(?<![.\w]){re.escape(name)}\b", f"{alias}.{name}", result)
        return result

    def _render_instance(self, instance: Instance) -> str:
        if instance.name in self._ctes:
            return _sql_name(instance.name)
        if instance.name in self._building:
            raise ValueError(f"Cycle detected while rendering {instance.name!r}")
        self._building.add(instance.name)

        if "source" in instance.instance_type.casefold():
            relation = f"{{{{ ref('{_relation_ref_name(instance)}') }}}}"
            self._building.remove(instance.name)
            return relation

        definition = self._definitions.get(instance.definition_name)
        if definition is None:
            raise ValueError(f"No transformation definition for instance {instance.name!r}")
        incoming = tuple(self.mapping.iter_connections_to(instance.name))
        upstream_instances = tuple(dict.fromkeys(connection.from_instance for connection in incoming))
        if not upstream_instances:
            raise ValueError(f"Transformation instance {instance.name!r} has no input connector")
        relations = [self._render_instance(self._instances[name]) for name in upstream_instances]
        aliases = [f"i{index}" for index in range(len(relations))]
        from_sql = f"{relations[0]} AS {aliases[0]}"
        for alias, relation in zip(aliases[1:], relations[1:]):
            from_sql += f"\nJOIN {relation} AS {alias} ON 1 = 1"

        incoming_by_field = {connection.to_field: (aliases[upstream_instances.index(connection.from_instance)], connection.from_field)
                             for connection in incoming}
        properties = definition.properties
        join_condition = properties.get("Join Condition")
        if join_condition and len(aliases) > 1:
            from_sql = f"{relations[0]} AS {aliases[0]}"
            for index, (alias, relation) in enumerate(zip(aliases[1:], relations[1:]), 1):
                condition = join_condition
                for field, (field_alias, _) in incoming_by_field.items():
                    condition = re.sub(rf"\b{re.escape(field)}\b", f"{field_alias}.{field}", condition)
                from_sql += f"\nJOIN {relation} AS {alias} ON {condition}"

        output_fields = tuple(field for field in definition.fields
                              if field.attributes.get("PORTTYPE", "").upper() in {"OUTPUT", "INPUT/OUTPUT"})
        select_lines: list[str] = []
        for field in output_fields:
            expression = translate_expression(field.expression)
            if not expression:
                input_info = incoming_by_field.get(field.name)
                expression = f"{input_info[0]}.{input_info[1]}" if input_info else field.name
            else:
                expression = self._qualify_expression(expression, incoming_by_field)
            select_lines.append(f"    {expression} AS {field.name}")
        if not select_lines:
            select_lines.append("    *")
        cte_name = _sql_name(instance.name)
        self._ctes[instance.name] = f"{cte_name} AS (\nSELECT\n{',\n'.join(select_lines)}\nFROM {from_sql}\n)"
        self._building.remove(instance.name)
        return cte_name


def generate_model_sql(
    mapping: Mapping,
    document: PowerCenterDocument,
    target_instance: str,
    source_name: str = "raw",
) -> str:
    """Generate dbt SQL for one target instance."""
    validate_or_raise(document)
    generator = DbtModelGenerator(mapping, document, source_name)
    target = mapping.find_instance(target_instance)
    if target is None:
        raise KeyError(f"Unknown target instance: {target_instance}")
    return generator.render_target(target)


def generate_dbt_models(
    document: PowerCenterDocument,
    output_dir: str | Path,
    source_name: str = "raw",
) -> tuple[Path, ...]:
    """Write dbt model SQL files for every target in every mapping."""
    validate_or_raise(document)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for mapping in document.mappings:
        targets = DbtModelGenerator(mapping, document, source_name).target_instances()
        for target in targets:
            generator = DbtModelGenerator(mapping, document, source_name)
            path = destination / f"{_sql_name(target.definition_name)}.sql"
            path.write_text(generator.render_target(target), encoding="utf-8")
            written.append(path)
    return tuple(written)


def generate_workflow_models(
    document: PowerCenterDocument,
    workflow: Workflow,
    output_dir: str | Path,
    source_name: str = "raw",
) -> tuple[Path, ...]:
    """Write models for sessions in workflow execution order."""
    validate_or_raise(document)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    generated_mappings: set[str] = set()
    for session in workflow_execution_plan(workflow, document):
        if session.mapping_name in generated_mappings:
            continue
        mapping = document.find_mapping(session.mapping_name)
        if mapping is None:
            raise ValueError(f"Session {session.name!r} references unknown mapping {session.mapping_name!r}")
        for target in DbtModelGenerator(mapping, document, source_name).target_instances():
            generator = DbtModelGenerator(mapping, document, source_name)
            path = destination / f"{_sql_name(target.definition_name)}.sql"
            path.write_text(generator.render_target(target), encoding="utf-8")
            written.append(path)
        generated_mappings.add(session.mapping_name)
    return tuple(written)
