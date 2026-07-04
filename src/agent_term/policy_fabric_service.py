"""Service-backed Policy Fabric backends.

AgentTerm is not the authority for policy. This module adds file and HTTP decision
lookup seams behind the existing PolicyFabricBackend protocol while keeping CI
offline-safe and fail-closed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

from agent_term.config import AgentTermConfig
from agent_term.events import AgentTermEvent
from agent_term.policy_fabric import PolicyDecision, PolicyFabricBackend, action_for_event


class PolicyFabricServiceError(RuntimeError):
    """Raised when a service-backed Policy Fabric lookup cannot be completed."""


class JsonFilePolicyFabricBackend:
    """Policy Fabric backend backed by a local JSON fixture file.

    Supported shape:

    ```json
    {
      "decisions": [
        {
          "decision_id": "decision.allow.github.pr.create",
          "action": "github.pr.create",
          "status": "allow",
          "policy_ref": "policy://github/pr-create"
        }
      ]
    }
    ```
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._decisions = self._load()

    def evaluate(self, event: AgentTermEvent) -> PolicyDecision | None:
        return self._decisions.get(action_for_event(event))

    def _load(self) -> dict[str, PolicyDecision]:
        with self.path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            raise ValueError("Policy Fabric fixture must be a JSON object")
        decisions = (_decision_from_record(record) for record in _records(raw.get("decisions")))
        return {decision.action: decision for decision in decisions}


class HttpPolicyFabricBackend:
    """Minimal HTTP Policy Fabric backend.

    Expected endpoint:

    - `GET {endpoint}/decisions/{action}` returns a policy decision object or 404.

    A bearer value is optional and read from an environment variable, never JSON config.
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

    def evaluate(self, event: AgentTermEvent) -> PolicyDecision | None:
        action = action_for_event(event)
        record = self._get_json(f"decisions/{quote(action, safe='')}")
        return _decision_from_record(record) if record is not None else None

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
            raise PolicyFabricServiceError(f"Policy Fabric HTTP error {exc.code}: {url}") from exc
        except URLError as exc:
            raise PolicyFabricServiceError(f"Policy Fabric connection error: {url}") from exc
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise PolicyFabricServiceError("Policy Fabric response must be a JSON object")
        return value


def build_policy_fabric_backend_from_config(
    config: AgentTermConfig,
    *,
    fallback: PolicyFabricBackend,
) -> PolicyFabricBackend:
    """Build a Policy Fabric backend from config, falling back to local fixtures."""

    if config.policy_fabric.fixture_path:
        return JsonFilePolicyFabricBackend(config.policy_fabric.fixture_path)

    if config.policy_fabric.endpoint_url:
        return HttpPolicyFabricBackend(
            endpoint_url=config.policy_fabric.endpoint_url,
            token=os.environ.get(config.policy_fabric.token_env),
            timeout_seconds=config.policy_fabric.timeout_seconds,
        )

    return fallback


def _records(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    return []


def _decision_from_record(record: dict[str, Any]) -> PolicyDecision:
    known = {
        "decision_id",
        "decisionId",
        "action",
        "status",
        "policy_ref",
        "policyRef",
        "reason",
        "obligations",
    }
    obligations_raw = record.get("obligations") or []
    obligations = tuple(str(item) for item in obligations_raw if item is not None)
    return PolicyDecision(
        decision_id=str(record.get("decision_id") or record.get("decisionId")),
        action=str(record.get("action")),
        status=str(record.get("status")),
        policy_ref=str(record.get("policy_ref") or record.get("policyRef")),
        reason=_optional_str(record.get("reason")),
        obligations=obligations,
        metadata={key: value for key, value in record.items() if key not in known},
    )


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
