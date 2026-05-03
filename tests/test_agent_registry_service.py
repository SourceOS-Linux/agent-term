import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from agent_term.agent_registry import InMemoryAgentRegistryBackend
from agent_term.agent_registry_service import (
    HttpAgentRegistryBackend,
    JsonFileAgentRegistryBackend,
    build_agent_registry_backend_from_config,
)
from agent_term.config import config_from_dict


def test_json_file_agent_registry_backend_resolves_agent_and_grant(tmp_path):
    fixture = tmp_path / "agent-registry.json"
    fixture.write_text(
        json.dumps(
            {
                "agents": [
                    {
                        "agent_id": "agent.codex",
                        "registry_ref": "fixture://agent.codex",
                        "spec_version": "v1",
                        "session_id": "session-codex",
                        "tool_grants": ["grant.repo-write"],
                    }
                ],
                "tool_grants": [
                    {
                        "grant_id": "grant.repo-write",
                        "agent_id": "agent.codex",
                        "tool": "repo-write",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    backend = JsonFileAgentRegistryBackend(fixture)
    agent = backend.resolve_agent("agent.codex")
    grant = backend.resolve_tool_grant("agent.codex", "repo-write")

    assert agent is not None
    assert agent.agent_id == "agent.codex"
    assert agent.session_id == "session-codex"
    assert agent.tool_grants == frozenset({"grant.repo-write"})
    assert grant is not None
    assert grant.grant_id == "grant.repo-write"
    assert grant.is_active is True


def test_json_file_agent_registry_backend_returns_none_for_unknowns(tmp_path):
    fixture = tmp_path / "agent-registry.json"
    fixture.write_text(json.dumps({"agents": [], "tool_grants": []}), encoding="utf-8")

    backend = JsonFileAgentRegistryBackend(fixture)

    assert backend.resolve_agent("agent.unknown") is None
    assert backend.resolve_tool_grant("agent.unknown", "repo-write") is None


def test_build_agent_registry_backend_uses_fixture_path(tmp_path):
    fixture = tmp_path / "agent-registry.json"
    fixture.write_text(
        json.dumps(
            {
                "agents": [{"agent_id": "agent.github", "spec_version": "v1"}],
                "tool_grants": [],
            }
        ),
        encoding="utf-8",
    )
    config = config_from_dict({"agentRegistration": {"fixturePath": str(fixture)}})

    backend = build_agent_registry_backend_from_config(
        config,
        fallback=InMemoryAgentRegistryBackend(),
    )

    assert isinstance(backend, JsonFileAgentRegistryBackend)
    assert backend.resolve_agent("agent.github") is not None


def test_build_agent_registry_backend_uses_fallback_without_service_config():
    fallback = InMemoryAgentRegistryBackend()

    backend = build_agent_registry_backend_from_config(config_from_dict({}), fallback=fallback)

    assert backend is fallback


def test_http_agent_registry_backend_resolves_agent_and_grant():
    server = _AgentRegistryHttpFixtureServer()
    try:
        backend = HttpAgentRegistryBackend(endpoint_url=server.url)

        agent = backend.resolve_agent("agent.codex")
        grant = backend.resolve_tool_grant("agent.codex", "repo-write")
        missing = backend.resolve_agent("agent.missing")
    finally:
        server.close()

    assert agent is not None
    assert agent.agent_id == "agent.codex"
    assert agent.spec_version == "v1"
    assert grant is not None
    assert grant.grant_id == "grant.repo-write"
    assert missing is None


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/agents/agent.codex":
            self._send(
                200,
                {
                    "agent_id": "agent.codex",
                    "registry_ref": "http://registry/agent.codex",
                    "spec_version": "v1",
                    "status": "active",
                },
            )
            return
        if self.path == "/agents/agent.codex/grants/repo-write":
            self._send(
                200,
                {
                    "grant_id": "grant.repo-write",
                    "agent_id": "agent.codex",
                    "tool": "repo-write",
                    "status": "active",
                },
            )
            return
        self._send(404, {"error": "not found"})

    def log_message(self, format, *args):  # noqa: A002
        return

    def _send(self, status, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class _AgentRegistryHttpFixtureServer:
    def __init__(self):
        self._server = HTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        host, port = self._server.server_address
        self.url = f"http://{host}:{port}/"

    def close(self):
        self._server.shutdown()
        self._thread.join(timeout=5)
        self._server.server_close()
