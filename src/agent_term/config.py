"""AgentTerm runtime configuration loading.

Configuration is intentionally declarative. It can describe local/default pipeline
posture and desired participant bindings, but it does not become authority for
agents, policy, Matrix, or any SourceOS plane.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_term.pipeline import DispatchPipelineConfig
from agent_term.store import DEFAULT_DB_PATH


@dataclass(frozen=True)
class EventStoreConfig:
    driver: str = "sqlite"
    path: str = str(DEFAULT_DB_PATH)


@dataclass(frozen=True)
class MatrixConfig:
    enabled: bool = False
    homeserver_url: str | None = None
    user_id: str | None = None
    device_name: str | None = None
    rooms: dict[str, str] = field(default_factory=dict)
    require_encrypted_room_posture_for_sensitive_context: bool = True
    preserve_bridge_metadata: bool = True
    preserve_redactions: bool = True
    preserve_membership_events: bool = True


@dataclass(frozen=True)
class AgentRegistrationConfig:
    require_registered_participants: bool = True
    fail_closed_when_registry_unavailable: bool = True
    repository: str = "SocioProphet/agent-registry"
    required_for: tuple[str, ...] = ()
    fixture_path: str | None = None
    endpoint_url: str | None = None
    token_env: str = "AGENT_TERM_AGENT_REGISTRY_TOKEN"
    timeout_seconds: float = 5.0


@dataclass(frozen=True)
class ParticipantConfig:
    key: str
    enabled: bool = False
    mode: str | None = None
    require_agent_registry_resolution: bool = True
    agent_registry_id: str | None = None
    require_policy_approval_for_mutation: bool = False
    require_policy_approval_for_side_effects: bool = False
    disable_for_sensitive_context: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PlaneConfig:
    key: str
    enabled: bool = False
    repository: str | None = None
    role: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class LocalRuntimeFixture:
    """Local test/dev fixture for the in-memory runtime backends."""

    registered_agents: tuple[str, ...] = ()
    tool_grants: tuple[str, ...] = ()
    allow_policies: tuple[str, ...] = ()
    deny_policies: tuple[str, ...] = ()
    pending_policies: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentTermConfig:
    workspace: str = "sourceos"
    default_channel: str = "!sourceos-ops"
    event_store: EventStoreConfig = field(default_factory=EventStoreConfig)
    matrix: MatrixConfig = field(default_factory=MatrixConfig)
    agent_registration: AgentRegistrationConfig = field(default_factory=AgentRegistrationConfig)
    planes: dict[str, PlaneConfig] = field(default_factory=dict)
    participants: dict[str, ParticipantConfig] = field(default_factory=dict)
    local_runtime: LocalRuntimeFixture = field(default_factory=LocalRuntimeFixture)
    raw: dict[str, object] = field(default_factory=dict)

    def pipeline_config(self) -> DispatchPipelineConfig:
        return DispatchPipelineConfig(
            require_matrix_posture_for_sensitive_context=(
                self.matrix.require_encrypted_room_posture_for_sensitive_context
            ),
            require_agent_registry_for_participants=(
                self.agent_registration.require_registered_participants
            ),
            require_policy_for_admitted_events=True,
        )

    def participant_agent_id(self, participant: str) -> str | None:
        config = self.participants.get(participant)
        return config.agent_registry_id if config else None



def load_config(path: Path | str | None) -> AgentTermConfig:
    if path is None:
        return AgentTermConfig()
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("AgentTerm config must be a JSON object")
    return config_from_dict(raw)


def config_from_dict(raw: dict[str, Any]) -> AgentTermConfig:
    event_store_raw = _dict(raw.get("eventStore"))
    matrix_raw = _dict(raw.get("matrix"))
    registration_raw = _dict(raw.get("agentRegistration"))
    participants_raw = _dict(raw.get("participants"))
    planes_raw = _dict(raw.get("planes"))
    local_runtime_raw = _dict(raw.get("localRuntime"))

    participants = {
        key: _participant_config(key, _dict(value)) for key, value in participants_raw.items()
    }
    planes = {key: _plane_config(key, _dict(value)) for key, value in planes_raw.items()}

    return AgentTermConfig(
        workspace=str(raw.get("workspace") or "sourceos"),
        default_channel=str(raw.get("defaultChannel") or "!sourceos-ops"),
        event_store=EventStoreConfig(
            driver=str(event_store_raw.get("driver") or "sqlite"),
            path=str(event_store_raw.get("path") or DEFAULT_DB_PATH),
        ),
        matrix=MatrixConfig(
            enabled=bool(matrix_raw.get("enabled", False)),
            homeserver_url=_optional_str(matrix_raw.get("homeserverUrl")),
            user_id=_optional_str(matrix_raw.get("userId")),
            device_name=_optional_str(matrix_raw.get("deviceName")),
            rooms={str(key): str(value) for key, value in _dict(matrix_raw.get("rooms")).items()},
            require_encrypted_room_posture_for_sensitive_context=bool(
                matrix_raw.get("requireEncryptedRoomPostureForSensitiveContext", True)
            ),
            preserve_bridge_metadata=bool(matrix_raw.get("preserveBridgeMetadata", True)),
            preserve_redactions=bool(matrix_raw.get("preserveRedactions", True)),
            preserve_membership_events=bool(matrix_raw.get("preserveMembershipEvents", True)),
        ),
        agent_registration=AgentRegistrationConfig(
            require_registered_participants=bool(
                registration_raw.get("requireRegisteredParticipants", True)
            ),
            fail_closed_when_registry_unavailable=bool(
                registration_raw.get("failClosedWhenRegistryUnavailable", True)
            ),
            repository=str(registration_raw.get("repository") or "SocioProphet/agent-registry"),
            required_for=tuple(str(item) for item in _list(registration_raw.get("requiredFor"))),
            fixture_path=_optional_str(registration_raw.get("fixturePath")),
            endpoint_url=_optional_str(registration_raw.get("endpointUrl")),
            token_env=str(registration_raw.get("tokenEnv") or "AGENT_TERM_AGENT_REGISTRY_TOKEN"),
            timeout_seconds=float(registration_raw.get("timeoutSeconds") or 5.0),
        ),
        planes=planes,
        participants=participants,
        local_runtime=LocalRuntimeFixture(
            registered_agents=tuple(
                str(item) for item in _list(local_runtime_raw.get("registeredAgents"))
            ),
            tool_grants=tuple(str(item) for item in _list(local_runtime_raw.get("toolGrants"))),
            allow_policies=tuple(str(item) for item in _list(local_runtime_raw.get("allowPolicies"))),
            deny_policies=tuple(str(item) for item in _list(local_runtime_raw.get("denyPolicies"))),
            pending_policies=tuple(
                str(item) for item in _list(local_runtime_raw.get("pendingPolicies"))
            ),
        ),
        raw=raw,
    )


def _participant_config(key: str, raw: dict[str, Any]) -> ParticipantConfig:
    known = {
        "enabled",
        "mode",
        "requireAgentRegistryResolution",
        "agentRegistryId",
        "requirePolicyApprovalForMutation",
        "requirePolicyApprovalForSideEffects",
        "disableForSensitiveContext",
    }
    return ParticipantConfig(
        key=key,
        enabled=bool(raw.get("enabled", False)),
        mode=_optional_str(raw.get("mode")),
        require_agent_registry_resolution=bool(raw.get("requireAgentRegistryResolution", True)),
        agent_registry_id=_optional_str(raw.get("agentRegistryId")),
        require_policy_approval_for_mutation=bool(
            raw.get("requirePolicyApprovalForMutation", False)
        ),
        require_policy_approval_for_side_effects=bool(
            raw.get("requirePolicyApprovalForSideEffects", False)
        ),
        disable_for_sensitive_context=bool(raw.get("disableForSensitiveContext", False)),
        metadata={key_: value for key_, value in raw.items() if key_ not in known},
    )


def _plane_config(key: str, raw: dict[str, Any]) -> PlaneConfig:
    known = {"enabled", "repository", "role"}
    return PlaneConfig(
        key=key,
        enabled=bool(raw.get("enabled", False)),
        repository=_optional_str(raw.get("repository")),
        role=_optional_str(raw.get("role")),
        metadata={key_: value for key_, value in raw.items() if key_ not in known},
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
