"""SourceOS interaction event support for AgentTerm.

AgentTerm is the operator surface. This module lets the terminal ingest and render the
shared SourceOSInteractionEvent contract without becoming the memory, policy, routing,
or execution authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_term.events import AgentTermEvent

JsonObject = dict[str, Any]

REQUIRED_TOP_LEVEL = {
    "interactionEventId",
    "type",
    "specVersion",
    "eventClass",
    "occurredAt",
    "surface",
    "mode",
    "session",
    "actor",
    "payloadMode",
    "governanceTrace",
}

REQUIRED_GOVERNANCE = {"policyAdmitted", "memoryWritten"}


def load_interaction_event(path: Path | str) -> JsonObject:
    """Load a SourceOSInteractionEvent JSON object from disk."""

    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)

    if not isinstance(value, dict):
        raise ValueError("SourceOSInteractionEvent payload must be a JSON object")
    return value


def validate_interaction_event(event: JsonObject) -> list[str]:
    """Return structural validation errors for AgentTerm's render/ingest boundary.

    This is intentionally a focused local check rather than a full JSON Schema validator.
    Full schema validation belongs to sourceos-spec CI. AgentTerm needs enough validation
    to fail closed before rendering or recording malformed events.
    """

    errors: list[str] = []

    for field in sorted(REQUIRED_TOP_LEVEL):
        if field not in event:
            errors.append(f"missing top-level field: {field}")

    if event.get("type") != "SourceOSInteractionEvent":
        errors.append("type must be SourceOSInteractionEvent")

    surface = event.get("surface")
    if not isinstance(surface, dict):
        errors.append("surface must be an object")
    else:
        if not surface.get("surfaceKind"):
            errors.append("surface.surfaceKind is required")
        if not surface.get("sourcePlane"):
            errors.append("surface.sourcePlane is required")

    session = event.get("session")
    if not isinstance(session, dict):
        errors.append("session must be an object")
    elif not session.get("sessionId"):
        errors.append("session.sessionId is required")

    actor = event.get("actor")
    if not isinstance(actor, dict):
        errors.append("actor must be an object")
    else:
        if not actor.get("actorRef"):
            errors.append("actor.actorRef is required")
        if not actor.get("actorKind"):
            errors.append("actor.actorKind is required")

    governance = event.get("governanceTrace")
    if not isinstance(governance, dict):
        errors.append("governanceTrace must be an object")
    else:
        for field in sorted(REQUIRED_GOVERNANCE):
            if field not in governance:
                errors.append(f"governanceTrace.{field} is required")

    return errors


def require_valid_interaction_event(event: JsonObject) -> None:
    """Raise a ValueError if the event fails local ingest checks."""

    errors = validate_interaction_event(event)
    if errors:
        raise ValueError("; ".join(errors))


def render_interaction_event(event: JsonObject) -> str:
    """Render a SourceOSInteractionEvent as an operator-readable governance trace."""

    require_valid_interaction_event(event)

    surface = _object(event, "surface")
    session = _object(event, "session")
    actor = _object(event, "actor")
    task = _nullable_object(event, "task")
    steering = _nullable_object(event, "steeringIntent")
    governance = _object(event, "governanceTrace")

    lines = [
        "SourceOS interaction event",
        f"  id: {event['interactionEventId']}",
        f"  class: {event['eventClass']}",
        f"  occurred: {event['occurredAt']}",
        f"  mode: {event['mode']}",
        f"  surface: {surface.get('surfaceKind')} ({surface.get('sourcePlane')})",
        f"  session: {session.get('sessionId')}",
        f"  actor: {actor.get('actorRef')} [{actor.get('actorKind')}]",
    ]

    if session.get("roomRef") or session.get("threadRef") or session.get("workroomRef"):
        lines.extend(
            [
                f"  room: {session.get('roomRef') or 'none'}",
                f"  thread: {session.get('threadRef') or 'none'}",
                f"  workroom: {session.get('workroomRef') or 'none'}",
                f"  topic: {session.get('topicRef') or 'none'}",
            ]
        )

    if task:
        latency = task.get("latencyMs") if task.get("latencyMs") is not None else "none"
        lines.extend(
            [
                "  task:",
                f"    status: {task.get('status')}",
                f"    provider: {task.get('provider') or 'none'}",
                f"    model_hint: {task.get('modelHint') or 'none'}",
                f"    model_routed: {task.get('modelRouted') or 'none'}",
                f"    latency_ms: {latency}",
            ]
        )

    if steering:
        lines.extend(
            [
                "  steering:",
                f"    kind: {steering.get('steeringKind')}",
                f"    status: {steering.get('status')}",
                f"    feature: {steering.get('featureRef') or 'none'}",
            ]
        )

    lines.extend(
        [
            "  governance:",
            f"    policy: {'admitted' if governance.get('policyAdmitted') else 'blocked'}",
            f"    policy_ref: {governance.get('policyRef') or 'none'}",
            f"    memory: {'written' if governance.get('memoryWritten') else 'not-written'}",
            f"    memory_scope: {governance.get('memoryScopeRef') or 'none'}",
            f"    request_hash: {governance.get('requestHash') or 'none'}",
            f"    evidence_hash: {governance.get('evidenceHash') or 'none'}",
            f"    provider_route_evidence: {governance.get('providerRouteEvidenceRef') or 'none'}",
            f"    agentplane_run: {governance.get('agentPlaneRunRef') or 'none'}",
            f"    replay: {governance.get('replayRef') or 'none'}",
        ]
    )

    _append_list(lines, "policy_decisions", governance.get("policyDecisionRefs"))
    _append_list(lines, "grants", governance.get("grantRefs"))
    _append_list(lines, "context_packs", governance.get("contextPackRefs"))
    _append_list(lines, "evidence", governance.get("evidenceRefs"))
    _append_list(lines, "redactions", event.get("redactionRefs"))

    payload = _nullable_object(event, "payload")
    if payload and isinstance(payload.get("summary"), str):
        lines.extend(["  payload:", f"    summary: {payload['summary']}"])
    elif event.get("payloadMode"):
        lines.extend(["  payload:", f"    mode: {event['payloadMode']}"])

    return "\n".join(lines)


def interaction_to_agent_term_event(
    event: JsonObject,
    *,
    channel: str = "!sourceos-interaction",
    sender: str = "@agent-term",
) -> AgentTermEvent:
    """Convert a SourceOSInteractionEvent into AgentTerm's local event model."""

    require_valid_interaction_event(event)

    surface = _object(event, "surface")
    session = _object(event, "session")
    governance = _object(event, "governanceTrace")
    task = _nullable_object(event, "task")
    payload = _nullable_object(event, "payload")

    body = _summary_body(event, payload, task)
    thread_id = session.get("threadRef") if isinstance(session.get("threadRef"), str) else None
    metadata: JsonObject = {
        "sourceos_interaction_event_id": event["interactionEventId"],
        "event_class": event["eventClass"],
        "mode": event["mode"],
        "surface": surface,
        "session": session,
        "task": task,
        "governanceTrace": governance,
        "payloadMode": event["payloadMode"],
        "sourceEventRefs": event.get("sourceEventRefs", []),
        "redactionRefs": event.get("redactionRefs", []),
    }

    return AgentTermEvent(
        channel=channel,
        sender=sender,
        kind="sourceos_interaction",
        source=str(surface.get("surfaceKind") or "sourceos-interaction"),
        body=body,
        thread_id=thread_id,
        metadata=metadata,
    )


def _summary_body(event: JsonObject, payload: JsonObject | None, task: JsonObject | None) -> str:
    if payload and isinstance(payload.get("summary"), str):
        return payload["summary"]
    if task:
        status = task.get("status", "unknown")
        provider = task.get("provider") or "unknown-provider"
        return f"{event['eventClass']} status={status} provider={provider}"
    return str(event["eventClass"])


def _object(event: JsonObject, key: str) -> JsonObject:
    value = event.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _nullable_object(event: JsonObject, key: str) -> JsonObject | None:
    value = event.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object or null")
    return value


def _append_list(lines: list[str], label: str, value: Any) -> None:
    if not value:
        lines.append(f"    {label}: none")
        return
    if not isinstance(value, list):
        lines.append(f"    {label}: invalid")
        return
    if not value:
        lines.append(f"    {label}: none")
        return
    lines.append(f"    {label}:")
    for item in value:
        lines.append(f"      - {item}")
