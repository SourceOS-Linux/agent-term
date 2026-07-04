"""Import Noetica SourceOSInteractionEvent artifact exports into AgentTerm."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_term.interaction import (
    interaction_to_agent_term_event,
    load_interaction_event,
    render_interaction_event,
)
from agent_term.store import EventStore


@dataclass(frozen=True)
class NoeticaImportResult:
    """Result summary for an opt-in Noetica artifact import."""

    imported: int
    paths: tuple[Path, ...]
    event_ids: tuple[str, ...]


def iter_noetica_interaction_artifacts(path: Path | str) -> list[Path]:
    """Return sorted Noetica interaction artifact paths from a file or directory."""

    root = Path(path)
    if root.is_file():
        return [root]
    if not root.exists():
        raise FileNotFoundError(f"Noetica interaction artifact path does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"Noetica interaction artifact path must be a file or directory: {root}")
    return sorted(p for p in root.glob("*.json") if p.is_file())


def import_noetica_interaction_artifacts(
    path: Path | str,
    store: EventStore,
    *,
    channel: str = "!sourceos-interaction",
    sender: str = "@agent-term",
    render: bool = False,
) -> NoeticaImportResult:
    """Record Noetica-exported SourceOSInteractionEvent JSON artifacts.

    This is deliberately pull/import based. AgentTerm remains an opt-in consumer and does
    not become part of Noetica's default desktop execution path.
    """

    paths = iter_noetica_interaction_artifacts(path)
    event_ids: list[str] = []

    for artifact_path in paths:
        interaction_event = load_interaction_event(artifact_path)
        agent_term_event = interaction_to_agent_term_event(
            interaction_event,
            channel=channel,
            sender=sender,
        )
        store.append(agent_term_event)
        event_ids.append(agent_term_event.event_id)
        if render:
            print(render_interaction_event(interaction_event))
            print(f"recorded: {agent_term_event.event_id}")

    return NoeticaImportResult(
        imported=len(paths),
        paths=tuple(paths),
        event_ids=tuple(event_ids),
    )
