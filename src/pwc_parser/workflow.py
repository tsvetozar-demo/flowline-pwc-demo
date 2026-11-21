"""Resolve PowerCenter workflow task instances into execution plans."""

from __future__ import annotations

from typing import Any

from .model import PowerCenterDocument, Session, Workflow


def workflow_execution_plan(workflow: Workflow, document: PowerCenterDocument) -> tuple[Session, ...]:
    """Return sessions in workflow dependency order."""
    tasks = {task.name: task for task in workflow.tasks}
    successors: dict[str, set[str]] = {name: set() for name in tasks}
    indegree = {name: 0 for name in tasks}
    for link in workflow.links:
        if link.from_task in tasks and link.to_task in tasks and link.to_task not in successors[link.from_task]:
            successors[link.from_task].add(link.to_task)
            indegree[link.to_task] += 1

    ready = [task.name for task in workflow.tasks if indegree[task.name] == 0]
    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for successor in successors[current]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
        ready.sort(key=lambda name: next(index for index, task in enumerate(workflow.tasks) if task.name == name))

    if len(ordered) != len(tasks):
        raise ValueError(f"Workflow {workflow.name!r} contains a cycle")

    sessions = {session.name: session for session in document.sessions}
    plan: list[Session] = []
    for task_name in ordered:
        task = tasks[task_name]
        if not task.is_session:
            continue
        session = sessions.get(task.task_name) or sessions.get(task.name)
        if session is None:
            raise ValueError(f"Workflow task {task.name!r} references an unknown session")
        plan.append(session)
    return tuple(plan)


def build_workflow_definition(
    workflow: Workflow,
    document: PowerCenterDocument,
) -> dict[str, Any]:
    """Return a JSON-like workflow structure with resolved sessions/mappings."""
    plan = workflow_execution_plan(workflow, document)
    return {
        "name": workflow.name,
        "attributes": dict(workflow.attributes),
        "tasks": {
            task.name: {
                **dict(task.attributes),
                "task_name": task.task_name,
                "task_type": task.task_type,
                "session": next((session.name for session in plan if session.name == task.task_name), None),
            }
            for task in workflow.tasks
        },
        "links": [dict(link.attributes) for link in workflow.links],
        "execution_plan": [
            {"session": session.name, "mapping": session.mapping_name}
            for session in plan
        ],
    }
