"""SourceOS plane registry for AgentTerm.

These records make SourceOS integration explicit at the CLI/event layer before any
network adapter is enabled. AgentTerm is the operator console; these planes own the
actual agent identity, workspace, semantic, memory, execution, policy, search, shell,
and orchestration semantics.
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
        key="agent-registry",
        display_name="Agent Registry",
        repository="SocioProphet/agent-registry",
        role="Governed registry for SocioProphet agent specs, identities, sessions, memories, tool grants, revocation, and runtime authority.",
        source="agent-registry",
        capabilities=(
            PlaneCapability("resolve_agent_identity", "Resolve an agent participant identity, spec, runtime authority, and registration state.", False, ("agent_identity",)),
            PlaneCapability("validate_agent_registration", "Validate that a requested AgentTerm participant is registered before enablement.", False, ("validation", "agent_identity")),
            PlaneCapability("request_tool_grant", "Request a governed tool/capability grant for an agent participant.", True, ("tool_grant", "policy_check")),
            PlaneCapability("revoke_agent_session", "Revoke or disable an agent session/capability grant.", True, ("revocation", "decision")),
        ),
        notes=(
            "Every non-human AgentTerm participant must be registered in Agent Registry before it is enabled.",
            "Hermes, Codex, Claude Code, OpenCLAW, GitHub bots, CI bots, MCP tools, Matrix bots, and local process agents should resolve identity and tool grants through Agent Registry.",
            "AgentTerm local config may reference participants, but Agent Registry remains the runtime authority for agent identity and grants.",
        ),
    ),
    SourceOSPlane(
        key="sociosphere",
        display_name="Sociosphere",
        repository="SocioProphet/sociosphere",
        role="Platform meta-workspace controller for canonical workspace manifests, dependency topology, governance registry, validation lanes, and release-readiness orchestration.",
        source="sociosphere",
        capabilities=(
            PlaneCapability("resolve_workspace_manifest", "Resolve canonical workspace repositories, roles, pins, and local overrides.", False, ("workspace_manifest",)),
            PlaneCapability("validate_topology", "Validate cross-repo directionality, dependency rules, and governance registry state.", False, ("validation",)),
            PlaneCapability("materialize_workspace", "Materialize a governed multi-repo workspace from the canonical manifest.", True, ("workspace_materialization",)),
        ),
        notes=(
            "Sociosphere is the meta-workspace controller; AgentTerm should display and request workspace operations, not own them.",
            "AgentTerm events should preserve manifest, lock, topology, and validation evidence references.",
        ),
    ),
    SourceOSPlane(
        key="prophet-workspace",
        display_name="Prophet Workspace",
        repository="SocioProphet/prophet-workspace",
        role="Open workspace product suite and Professional Workrooms contract surface for mail, calendar, drive, docs, chat, meetings, policy-aware UX, admin, audit, and search.",
        source="prophet-workspace",
        capabilities=(
            PlaneCapability("open_workroom", "Bind an AgentTerm thread to a Professional Workroom.", False, ("workroom",)),
            PlaneCapability("validate_workroom", "Validate Professional Workroom contracts and examples.", False, ("validation",)),
            PlaneCapability("hydrate_workspace_context", "Release policy-approved workspace context into an agent thread.", True, ("context_pack", "workroom")),
            PlaneCapability("record_workspace_receipt", "Record workspace audit, receipt, and provenance references.", False, ("evidence",)),
        ),
        notes=(
            "Prophet Workspace owns product/workroom semantics; Sociosphere owns meta-workspace manifest and topology.",
            "AgentTerm should map Matrix rooms and local threads to Professional Workrooms when available.",
        ),
    ),
    SourceOSPlane(
        key="slash-topics",
        display_name="Slash Topics",
        repository="SocioProphet/slash-topics",
        role="Governed, signed, replayable topic scopes for search and knowledge surfaces with policy membranes and deterministic receipts.",
        source="slash-topics",
        capabilities=(
            PlaneCapability("select_topic_scope", "Bind a slash-topic scope to a room, thread, workroom, or query.", False, ("topic_scope",)),
            PlaneCapability("validate_topic_pack", "Validate signed topic packs, schemas, and policy membranes.", False, ("validation",)),
            PlaneCapability("apply_topic_membrane", "Apply topic-policy gates before search, memory, or context release.", True, ("policy_check", "topic_scope")),
        ),
        notes=(
            "Slash Topics should route and constrain search, memory, Holmes/Sherlock investigation, and New Hope semantic threads.",
            "AgentTerm slash commands should preserve topic-pack IDs, signature state, membrane decisions, and replay receipts.",
        ),
    ),
    SourceOSPlane(
        key="memory-mesh",
        display_name="Memory Mesh",
        repository="SocioProphet/memory-mesh",
        role="Canonical memory runtime for recall, writeback, config watch, resource application, context packs, LiteLLM callbacks, and OpenCLAW memory tools.",
        source="memory-mesh",
        capabilities=(
            PlaneCapability("recall_context", "Recall scoped memory/context before an agent or investigation run.", True, ("memory_recall", "context_pack")),
            PlaneCapability("write_memory", "Write governed memory after an agent action or workroom event.", True, ("memory_write",)),
            PlaneCapability("validate_context_pack", "Validate Professional Intelligence context-pack contracts and examples.", False, ("validation",)),
            PlaneCapability("record_memory_evidence", "Record memory entries, source references, and evidence records.", False, ("evidence",)),
        ),
        notes=(
            "Memory Mesh should be used for governed recall/writeback, not ad hoc prompt stuffing.",
            "Context release should carry workroom, topic, policy, search-packet, and evidence references.",
        ),
    ),
    SourceOSPlane(
        key="new-hope",
        display_name="New Hope",
        repository="SocioProphet/new-hope",
        role="Higher-order semantic runtime for agentic commons over messages, threads, claims, citations, entities, lenses, receptors, membranes, and moderation events.",
        source="new-hope",
        capabilities=(
            PlaneCapability("normalize_thread", "Normalize Matrix/workspace/chat threads into New Hope semantic objects.", False, ("semantic_thread",)),
            PlaneCapability("extract_claims", "Extract governed claims, citations, entities, and lenses from a thread.", True, ("claim", "citation")),
            PlaneCapability("apply_semantic_membrane", "Apply New Hope receptor/membrane decisions before routing or ranking.", True, ("policy_check", "semantic_membrane")),
            PlaneCapability("record_moderation_event", "Record moderation/ranking/provenance decisions as replayable semantic events.", False, ("moderation_event", "evidence")),
        ),
        notes=(
            "New Hope is not covered by Holmes or Sherlock; it is the semantic runtime underneath message/thread/claim/citation operations.",
            "AgentTerm should use New Hope to normalize operator and agent conversations before routing them into Holmes/Sherlock/Memory Mesh where appropriate.",
        ),
    ),
    SourceOSPlane(
        key="holmes",
        display_name="Holmes",
        repository="SocioProphet/holmes",
        role="External language intelligence fabric for casefiles, retrieval, semantic graphs, synthesis, guardrails, evals, and investigative discovery.",
        source="holmes",
        capabilities=(
            PlaneCapability("open_casefile", "Request or correlate a Holmes-owned investigation or casefile.", True, ("casefile",)),
            PlaneCapability("investigate", "Request a governed Holmes investigation without redefining Holmes behavior.", True, ("investigation",)),
            PlaneCapability("correlate_holmes_artifact", "Record Holmes-owned artifact, status, eval, guardrail, synthesis, or evidence references.", False, ("evidence", "correlation")),
        ),
        notes=(
            "AgentTerm must not define Holmes product semantics, schemas, service behavior, model routing, or deployment.",
            "AgentTerm may request, display, correlate, and audit Holmes-owned work once Holmes exposes stable contracts.",
            "Holmes integration must respect docs/integration/holmes-boundary.md.",
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
            "Search packets should carry provenance, scope, policy state, topic scope, memory references, and workroom/thread binding.",
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
    SourceOSPlane(
        key="meshrush",
        display_name="MeshRush",
        repository="SocioProphet/meshrush",
        role="Graph-native autonomous-agent protocol and reference runtime for operating over graph views derived from typed hypergraph world models.",
        source="meshrush",
        capabilities=(
            PlaneCapability("enter_graph_view", "Bind an agent or workroom thread to a typed graph view.", True, ("graph_view",)),
            PlaneCapability("diffuse_graph", "Run governed graph diffusion/exploration while preserving provenance.", True, ("graph_diffusion",)),
            PlaneCapability("crystallize_artifact", "Persist stable local graph structure and derived artifacts.", True, ("graph_artifact", "evidence")),
            PlaneCapability("record_graph_trace", "Record traces and learning/evaluation surfaces for adjacent systems.", False, ("trace", "evidence")),
        ),
        notes=(
            "MeshRush is the graph-operating runtime; it does not replace Sociosphere, AgentPlane, Prophet Workspace, or Holmes.",
            "AgentTerm should expose graph operations as visible, policy-aware events with provenance and reversibility metadata.",
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
)


def iter_planes() -> Iterable[SourceOSPlane]:
    return iter(SOURCEOS_PLANES)


def get_plane(key: str) -> SourceOSPlane:
    for plane in SOURCEOS_PLANES:
        if plane.key == key:
            return plane
    raise KeyError(f"unknown SourceOS plane: {key}")
