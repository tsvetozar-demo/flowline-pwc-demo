"""Structural validation for parsed PowerCenter documents."""

from __future__ import annotations

from dataclasses import dataclass

from .model import Definition, Mapping, PowerCenterDocument
from .workflow import workflow_execution_plan


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.code} at {self.path}: {self.message}"


class DocumentValidationError(ValueError):
    def __init__(self, issues: tuple[ValidationIssue, ...]):
        self.issues = issues
        super().__init__("\n".join(str(issue) for issue in issues))


def _duplicates(names: list[str]) -> set[str]:
    return {name for name in names if name and names.count(name) > 1}


def _definition_fields(definition: Definition) -> set[str]:
    return {field.name.casefold() for field in definition.fields if field.name}


def validate_document(document: PowerCenterDocument) -> tuple[ValidationIssue, ...]:
    """Return all structural issues found in a parsed document.

    Validation is intentionally non-throwing so callers can display every
    problem in one pass. Use :func:`validate_or_raise` when generation must
    stop on invalid input.
    """
    issues: list[ValidationIssue] = []
    mappings = {mapping.name: mapping for mapping in document.mappings if mapping.name}
    mapping_names = [mapping.name for mapping in document.mappings]
    for name in _duplicates(mapping_names):
        issues.append(ValidationIssue("DUPLICATE_MAPPING", f"mapping[{name}]", "mapping name is not unique"))
    for index, mapping in enumerate(document.mappings):
        mapping_path = f"mapping[{mapping.name or index}]"
        if not mapping.name:
            issues.append(ValidationIssue("MISSING_NAME", mapping_path, "mapping has no NAME"))
        _validate_mapping(mapping, document, issues, mapping_path)

    session_names = [session.name for session in document.sessions]
    for name in _duplicates(session_names):
        issues.append(ValidationIssue("DUPLICATE_SESSION", f"session[{name}]", "session name is not unique"))
    sessions = {session.name: session for session in document.sessions if session.name}
    for index, session in enumerate(document.sessions):
        path = f"session[{session.name or index}]"
        if not session.name:
            issues.append(ValidationIssue("MISSING_NAME", path, "session has no NAME"))
        if not session.mapping_name:
            issues.append(ValidationIssue("MISSING_MAPPING", path, "session has no MAPPINGNAME"))
        elif session.mapping_name not in mappings:
            issues.append(ValidationIssue("UNKNOWN_MAPPING", path, f"mapping {session.mapping_name!r} does not exist"))

    workflow_names = [workflow.name for workflow in document.workflows]
    for name in _duplicates(workflow_names):
        issues.append(ValidationIssue("DUPLICATE_WORKFLOW", f"workflow[{name}]", "workflow name is not unique"))
    for index, workflow in enumerate(document.workflows):
        path = f"workflow[{workflow.name or index}]"
        if not workflow.name:
            issues.append(ValidationIssue("MISSING_NAME", path, "workflow has no NAME"))
        task_names = [task.name for task in workflow.tasks]
        task_set = {name for name in task_names if name}
        for name in _duplicates(task_names):
            issues.append(ValidationIssue("DUPLICATE_TASK", f"{path}.task[{name}]", "task name is not unique"))
        for task in workflow.tasks:
            task_path = f"{path}.task[{task.name or '<unnamed>'}]"
            if not task.name:
                issues.append(ValidationIssue("MISSING_NAME", task_path, "task has no NAME"))
            if task.is_session:
                session_name = task.task_name or task.name
                if session_name not in sessions:
                    issues.append(ValidationIssue("UNKNOWN_SESSION", task_path, f"session {session_name!r} does not exist"))
        for link in workflow.links:
            link_path = f"{path}.link[{link.from_task}->{link.to_task}]"
            if link.from_task not in task_set:
                issues.append(ValidationIssue("UNKNOWN_TASK", link_path, f"source task {link.from_task!r} does not exist"))
            if link.to_task not in task_set:
                issues.append(ValidationIssue("UNKNOWN_TASK", link_path, f"target task {link.to_task!r} does not exist"))
        if not any(issue.path == path and issue.code in {"UNKNOWN_SESSION", "UNKNOWN_TASK"} for issue in issues):
            try:
                workflow_execution_plan(workflow, document)
            except ValueError as error:
                issues.append(ValidationIssue("WORKFLOW_CYCLE", path, str(error)))
    return tuple(issues)


def _validate_mapping(
    mapping: Mapping,
    document: PowerCenterDocument,
    issues: list[ValidationIssue],
    path: str,
) -> None:
    transformations = {item.name: item for item in mapping.transformations if item.name}
    instances = {item.name: item for item in mapping.instances if item.name}
    sources = {item.name: item for item in document.sources if item.name}
    targets = {item.name: item for item in document.targets if item.name}
    for label, names in (
        ("TRANSFORMATION", [item.name for item in mapping.transformations]),
        ("INSTANCE", [item.name for item in mapping.instances]),
    ):
        for name in _duplicates(names):
            issues.append(ValidationIssue(f"DUPLICATE_{label}", f"{path}.{label.lower()}[{name}]", "name is not unique"))
    for index, instance in enumerate(mapping.instances):
        instance_path = f"{path}.instance[{instance.name or index}]"
        if not instance.name:
            issues.append(ValidationIssue("MISSING_NAME", instance_path, "instance has no NAME"))
        kind = instance.instance_type.casefold()
        if "source" in kind:
            definition = sources.get(instance.definition_name)
            if definition is None:
                issues.append(ValidationIssue("UNKNOWN_SOURCE", instance_path, f"source {instance.definition_name!r} does not exist"))
        elif "target" in kind:
            definition = targets.get(instance.definition_name)
            if definition is None:
                issues.append(ValidationIssue("UNKNOWN_TARGET", instance_path, f"target {instance.definition_name!r} does not exist"))
        elif instance.definition_name not in transformations:
            issues.append(ValidationIssue("UNKNOWN_TRANSFORMATION", instance_path, f"transformation {instance.definition_name!r} does not exist"))
    for connection in mapping.connections:
        connection_path = f"{path}.connector[{connection.from_instance}.{connection.from_field}->{connection.to_instance}.{connection.to_field}]"
        source_instance = instances.get(connection.from_instance)
        target_instance = instances.get(connection.to_instance)
        if source_instance is None:
            issues.append(ValidationIssue("UNKNOWN_INSTANCE", connection_path, f"from instance {connection.from_instance!r} does not exist"))
        if target_instance is None:
            issues.append(ValidationIssue("UNKNOWN_INSTANCE", connection_path, f"to instance {connection.to_instance!r} does not exist"))
        if source_instance is not None:
            fields = _instance_fields(source_instance, transformations, sources, targets)
            if connection.from_field.casefold() not in fields:
                issues.append(ValidationIssue("UNKNOWN_PORT", connection_path, f"from field {connection.from_field!r} does not exist"))
        if target_instance is not None:
            fields = _instance_fields(target_instance, transformations, sources, targets)
            if connection.to_field.casefold() not in fields:
                issues.append(ValidationIssue("UNKNOWN_PORT", connection_path, f"to field {connection.to_field!r} does not exist"))


def _instance_fields(instance, transformations, sources, targets) -> set[str]:
    kind = instance.instance_type.casefold()
    if "source" in kind:
        definition = sources.get(instance.definition_name)
    elif "target" in kind:
        definition = targets.get(instance.definition_name)
    else:
        definition = transformations.get(instance.definition_name)
    return _definition_fields(definition) if definition else set()


def validate_or_raise(document: PowerCenterDocument) -> None:
    issues = validate_document(document)
    if issues:
        raise DocumentValidationError(issues)
