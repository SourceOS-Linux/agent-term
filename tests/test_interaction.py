"""Tests for SourceOSInteractionEvent rendering."""

from __future__ import annotations

from pathlib import Path

from agent_term.contracts.sourceos.generated.sourceos_interaction_event import (
    SOURCEOS_INTERACTION_EVENT_REQUIRED,
    SourceOSInteractionEvent,
)
from agent_term.interaction import (
    interaction_to_agent_term_event,
    load_interaction_event,
    render_interaction_event,
    validate_interaction_event,
)


FIXTURE = Path(__file__).parent / "fixtures" / "sourceos_interaction_event.json"


def test_generated_contract_artifact_is_importable() -> None:
    assert "interactionEventId" in SOURCEOS_INTERACTION_EVENT_REQUIRED
    assert "governanceTrace" in SOURCEOS_INTERACTION_EVENT_REQUIRED


def test_fixture_passes_local_required_field_checks() -> None:
    event = load_interaction_event(FIXTURE)

    assert validate_interaction_event(event) == []


def test_loaded_fixture_is_sourceos_interaction_event_typed_dict() -> None:
    event: SourceOSInteractionEvent = load_interaction_event(FIXTURE)

    assert event["type"] == "SourceOSInteractionEvent"
    assert event["governanceTrace"]["policyAdmitted"] is True


def test_render_interaction_event_exposes_governance_trace() -> None:
    event = load_interaction_event(FIXTURE)

    rendered = render_interaction_event(event)

    assert "SourceOS interaction event" in rendered
    assert "surface: noetica (SocioProphet/Noetica)" in rendered
    assert "policy: admitted" in rendered
    assert "memory: not-written" in rendered
    assert "provider: openai" in rendered
    assert "replay: urn:srcos:replay:noetica-standalone-0001" in rendered


def test_interaction_event_converts_to_agent_term_event() -> None:
    event = load_interaction_event(FIXTURE)

    converted = interaction_to_agent_term_event(
        event,
        channel="!demo",
        sender="@agent-term",
    )

    assert converted.channel == "!demo"
    assert converted.sender == "@agent-term"
    assert converted.kind == "sourceos_interaction"
    assert converted.source == "noetica"
    assert converted.thread_id == "urn:srcos:thread:noetica-local-demo"
    assert converted.metadata["event_class"] == "interaction.task_completed"
    assert converted.metadata["governanceTrace"]["policyAdmitted"] is True


def test_missing_governance_trace_fails_local_check() -> None:
    event = load_interaction_event(FIXTURE)
    event.pop("governanceTrace")

    assert "missing top-level field: governanceTrace" in validate_interaction_event(event)
