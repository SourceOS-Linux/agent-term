"""SourceOS plane registry for AgentTerm.

These records make SourceOS integration explicit at the CLI/event layer before any
network adapter is enabled. AgentTerm is the operator console; these planes own the
actual execution, policy, search, shell, and orchestration semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class PlaneCapability:
    """An operator-visible capability exposed by a SourceOS plane."""

    name: str
    description: str
    requires_approval: bool = True
    event_kinds: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceOSPlane:
    """A first-class SourceOS integration plane."""

    key: str
    display_name: str
    repository: str
    role: str
    source: str
    capabilities: tuple[PlaneCapability, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


SOURCEOS_PLANES: tuple[SourceOSPlane, ...] = (
    SourceOSPlane(
        key="matrix",
        display_name="Matrix",
        repository="external/matrix",
        role="Canonical federated ChatOps transport for rooms, events, membership, redactions, bridge metadata, and E2EE posture.",
        source="matrix",
        capabilities=(
            PlaneCapability("room_event_ingest", "Normalize Matrix room events into the AgentTerm event log.", False, ("message", "command")),
            PlaneCapability("room_event_emit", "Emit approved agent/operator events back into Matrix rooms.", True, ("message", "decision")),
            PlaneCapability("e2ee_posture_check", "Block sensitive context injection when encrypted-room posture is unknown or unsafe.", False, ("policy_check",)),
        ),
    ),
    SourceOSPlane(
        key="cloudshell-fog",
        display_name="CloudShell Fog",
        repository="SocioProphet/cloudshell-fog",
        role="Fog-first secure shell/session substrate for browser and terminal-accessible operator runtimes.",
        source="cloudshell-fog",
        capabilities=(
            PlaneCapability("request_shell_session", "Request a governed fog/cloud shell session.", True, ("shell_session", "command")),
            PlaneCapability("attach_pty", "Attach to an approved PTY/WebSocket session.", True, ("shell_attach",)),
            PlaneCapability("record_shell_audit", "Record session placement, identity, TTL, and audit metadata.", False, ("audit",)),
        ),
        notes=(
            "AgentTerm should not bypass cloudshell-fog policy, placement, OIDC, TTL, or audit semantics.",
            "Terminal UX must treat shell attach as a governed event, not an implicit local subprocess.",
        ),
    ),
    SourceOSPlane(
        key="agentplane",
        display_name="AgentPlane",
        repository="SocioProphet/agentplane",
        role="Execution control plane for validated bundles, executor placement, runs, replay, and evidence artifacts.",
        source="agentplane",
        capabilities=(
            PlaneCapability("validate_bundle", "Validate a bundle before execution.", False, ("validation",)),
            PlaneCapability("select_executor", "Choose an executor and emit a placement decision.", True, ("placement",)),
            PlaneCapability("run_bundle", "Run a governed bundle and emit run/replay artifacts.", True, ("run", "evidence")),
            PlaneCapability("replay_run", "Replay a governed run from recorded artifacts.", True, ("replay",)),
        ),
        notes=(
            "AgentTerm is the operator surface; AgentPlane remains the execution authority.",
            "RunArtifact, ReplayArtifact, ValidationArtifact, and PlacementDecision metadata should be preserved in AgentTerm events.",
        ),
    ),
    SourceOSPlane(
        key="policy-fabric",
        display_name="Policy Fabric",
        repository="SocioProphet/policy-fabric",
        role="Policy-as-code control repository for validating, packaging, reviewing, and releasing governed data-protection decisions.",
        source="policy-fabric",
        capabilities=(
            PlaneCapability("evaluate_command", "Evaluate slash commands before dispatch.", False, ("policy_check",)),
            PlaneCapability("approve_action", "Bind explicit approval decisions to operator identity and policy context.", True, ("decision",)),
            PlaneCapability("emit_policy_evidence", "Persist validation and replay evidence for governed actions.", False, ("evidence",)),
        ),
        notes=(
            "Every side-effecting adapter command should have a Policy Fabric decision point.",
            "Policy failures should be visible as first-class ChatOps events, not hidden exceptions.",
        ),
    ),
    SourceOSPlane(
        key="sherlock-search",
        display_name="Sherlock Search",
        repository="SocioProphet/sherlock-search",
        role="Canonical Sherlock retrieval/search-packet surface for professional intelligence, workroom-scoped context, and demo-grade discovery.",
        source="sherlock-search",
        capabilities=(
            PlaneCapability("create_search_packet", "Create a scoped search packet for a workroom/thread.", True, ("search_packet",)),
            PlaneCapability("validate_search_packet", "Validate Sherlock search-packet schema and examples.", False, ("validation",)),
            PlaneCapability("hydrate_context_pack", "Hydrate Matrix/AgentPlane/PolicyFabric context for retrieval-aware agent work.", True, ("context_pack",)),
        ),
        notes=(
            "This is the preferred Sherlock integration path for AgentTerm.",
            "Search packets should carry provenance, scope, policy state, and workroom/thread binding.",
        ),
    ),
    SourceOSPlane(
        key="legacy-sherlock",
        display_name="Legacy Sherlock OSINT",
        repository="SocioProphet/sherlock",
        role="Legacy username/social-network OSINT tool. Available only as a high-friction, policy-gated adapter.",
        source="legacy-sherlock",
        capabilities=(
            PlaneCapability("username_lookup", "Run bounded username discovery with explicit authorization and audit metadata.", True, ("osint_lookup",)),
        ),
        notes=(
            "Do not expose legacy Sherlock as a default agent tool.",
            "Use Policy Fabric approvals, scope limits, terms-of-use warnings, and audit receipts before invocation.",
        ),
    ),
)


def iter_planes() -> Iterable[SourceOSPlane]:
    return iter(SOURCEOS_PLANES)


def get_plane(key: str) -> SourceOSPlane:
    for plane in SOURCEOS_PLANES:
        if plane.key == key:
            return plane
    raise KeyError(f"unknown SourceOS plane: {key}")
