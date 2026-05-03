"""Service-backed Agent Registry backends.

AgentTerm is not the authority for agent identity. This module adds file and HTTP
service seams behind the existing AgentRegistryBackend protocol while keeping CI
offline-safe and fail-closed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

from agent_term.agent_registry import AgentRegistration, AgentRegistryBackend, ToolGrant
from agent_term.config import AgentTermConfig


class AgentRegistryServiceError(RuntimeError):
    """Raised when a service-backed Agent Registry lookup cannot be completed."""


@dataclass(frozen=True)
class AgentRegistryServiceConfig:
    """Configuration for service-backed Agent Registry lookups."""

    endpoint_url: str | None = None
    fixture_path: str | None = None
    token_env: str = "AGENT_TERM_AGENT_REGISTRY_TOKEN"
    timeout_seconds: float = 5.0


class JsonFileAgentRegistryBackend:
    """Agent Registry backend backed by a local JSON fixture file.

    Supported shape:

    ```json
    {
      "agents": [
        {"agent_id": "agent.codex", "registry_ref": "...", "spec_version": "v1"}
      ],
      "tool_grants": [
        {"grant_id": "grant.repo-write", "agent_id": "agent.codex", "tool": "repo-write"}
      ]
    }
    ```
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._agents, self._grants = self._load()

    def resolve_agent(self, agent_id: str) -> AgentRegistration | None:
        return self._agents.get(agent_id)

    def resolve_tool_grant(self, agent_id: str, tool: str) -> ToolGrant | None:
        return self._grants.get((agent_id, tool))

    def _load(self) -> tuple[dict[str, AgentRegistration], dict[tuple[str, str], ToolGrant]]:
        with self.path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            raise ValueError("Agent Registry fixture must be a JSON object")

        agents = {
            registration.agent_id: registration
            for registration in (_agent_from_record(record) for record in _records(raw.get("agents")))
        }
        grants = {
            (grant.agent_id, grant.tool): grant
            for grant in (_grant_from_record(record) for record in _records(raw.get("tool_grants")))
        }
        return agents, grants


class HttpAgentRegistryBackend:
    """Minimal HTTP Agent Registry backend.

    Expected endpoints are intentionally small and stable:

    - `GET {endpoint}/agents/{agent_id}` returns an agent registration object or 404.
    - `GET {endpoint}/agents/{agent_id}/grants/{tool}` returns a tool grant object or 404.

    A bearer token is optional and read from an environment variable, never JSON config.
    """

    def __init__(
        self,
        *,
        endpoint_url: str,
        token: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.endpoint_url = endpoint_url.rstrip("/") + "/"
        self.token = token
        self.timeout_seconds = timeout_seconds

    def resolve_agent(self, agent_id: str) -> AgentRegistration | None:
        record = self._get_json(f"agents/{quote(agent_id, safe='')}")
        return _agent_from_record(record) if record is not None else None

    def resolve_tool_grant(self, agent_id: str, tool: str) -> ToolGrant | None:
        record = self._get_json(
            f"agents/{quote(agent_id, safe='')}/grants/{quote(tool, safe='')}"
        )
        return _grant_from_record(record) if record is not None else None

    def _get_json(self, path: str) -> dict[str, Any] | None:
        url = urljoin(self.endpoint_url, path)
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code == 404:
                return None
            raise AgentRegistryServiceError(f"Agent Registry HTTP error {exc.code}: {url}") from exc
        except URLError as exc:
            raise AgentRegistryServiceError(f"Agent Registry connection error: {url}") from exc
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise AgentRegistryServiceError("Agent Registry response must be a JSON object")
        return value


def build_agent_registry_backend_from_config(
    config: AgentTermConfig,
    *,
    fallback: AgentRegistryBackend,
) -> AgentRegistryBackend:
    """Build an Agent Registry backend from config, falling back to local fixtures.

    Config can point to a local fixture or HTTP endpoint. If neither is configured,
    the provided fallback backend is returned.
    """

    fixture_path = getattr(config.agent_registration, "fixture_path", None)
    if fixture_path:
        return JsonFileAgentRegistryBackend(fixture_path)

    endpoint_url = getattr(config.agent_registration, "endpoint_url", None)
    if endpoint_url:
        token_env = getattr(config.agent_registration, "token_env", "AGENT_TERM_AGENT_REGISTRY_TOKEN")
        timeout_seconds = float(getattr(config.agent_registration, "timeout_seconds", 5.0))
        return HttpAgentRegistryBackend(
            endpoint_url=endpoint_url,
            token=os.environ.get(token_env),
            timeout_seconds=timeout_seconds,
        )

    return fallback


def _records(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    return []


def _agent_from_record(record: dict[str, Any]) -> AgentRegistration:
    agent_id = str(record.get("agent_id") or record.get("id") or record.get("agentId"))
    tool_grants_raw = record.get("tool_grants") or record.get("toolGrants") or []
    tool_grants = frozenset(str(item) for item in tool_grants_raw if item is not None)
    known = {
        "agent_id",
        "id",
        "agentId",
        "registry_ref",
        "registryRef",
        "spec_version",
        "specVersion",
        "runtime_authority",
        "runtimeAuthority",
        "status",
        "session_id",
        "sessionId",
        "tool_grants",
        "toolGrants",
        "revoked",
    }
    return AgentRegistration(
        agent_id=agent_id,
        registry_ref=str(record.get("registry_ref") or record.get("registryRef") or agent_id),
        spec_version=str(record.get("spec_version") or record.get("specVersion") or "unknown"),
        runtime_authority=str(
            record.get("runtime_authority") or record.get("runtimeAuthority") or "agent-registry"
        ),
        status=str(record.get("status") or "registered"),
        session_id=_optional_str(record.get("session_id") or record.get("sessionId")),
        tool_grants=tool_grants,
        revoked=bool(record.get("revoked", False)),
        metadata={key: value for key, value in record.items() if key not in known},
    )


def _grant_from_record(record: dict[str, Any]) -> ToolGrant:
    known = {"grant_id", "grantId", "agent_id", "agentId", "tool", "status"}
    return ToolGrant(
        grant_id=str(record.get("grant_id") or record.get("grantId")),
        agent_id=str(record.get("agent_id") or record.get("agentId")),
        tool=str(record.get("tool")),
        status=str(record.get("status") or "active"),
        metadata={key: value for key, value in record.items() if key not in known},
    )


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
