import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from agent_term.config import config_from_dict
from agent_term.events import AgentTermEvent
from agent_term.policy_fabric import ALLOW, DENY, InMemoryPolicyFabricBackend
from agent_term.policy_fabric_service import (
    HttpPolicyFabricBackend,
    JsonFilePolicyFabricBackend,
    build_policy_fabric_backend_from_config,
)


def make_event(action: str) -> AgentTermEvent:
    return AgentTermEvent(
        channel="!policyfabric",
        sender="@operator",
        kind="github_mutation",
        source="github",
        body="policy test",
        metadata={"policy_action": action},
    )


def test_json_file_policy_fabric_backend_resolves_decisions(tmp_path):
    fixture = tmp_path / "policy-fabric.json"
    fixture.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "decision_id": "decision.allow.github.pr.create",
                        "action": "github.pr.create",
                        "status": "allow",
                        "policy_ref": "fixture://policy/github-pr-create",
                        "obligations": ["record-audit"],
                    },
                    {
                        "decision_id": "decision.deny.github.repo.delete",
                        "action": "github.repo.delete",
                        "status": "deny",
                        "policy_ref": "fixture://policy/github-delete",
                        "reason": "repo delete not allowed",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    backend = JsonFilePolicyFabricBackend(fixture)
    allowed = backend.evaluate(make_event("github.pr.create"))
    denied = backend.evaluate(make_event("github.repo.delete"))
    missing = backend.evaluate(make_event("github.unknown"))

    assert allowed is not None
    assert allowed.status == ALLOW
    assert allowed.obligations == ("record-audit",)
    assert denied is not None
    assert denied.status == DENY
    assert denied.reason == "repo delete not allowed"
    assert missing is None


def test_build_policy_fabric_backend_uses_fixture_path(tmp_path):
    fixture = tmp_path / "policy-fabric.json"
    fixture.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "decision_id": "decision.allow.github.pr.create",
                        "action": "github.pr.create",
                        "status": "allow",
                        "policy_ref": "fixture://policy/github-pr-create",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config = config_from_dict({"policyFabric": {"fixturePath": str(fixture)}})

    backend = build_policy_fabric_backend_from_config(
        config,
        fallback=InMemoryPolicyFabricBackend(),
    )

    assert isinstance(backend, JsonFilePolicyFabricBackend)
    assert backend.evaluate(make_event("github.pr.create")) is not None


def test_build_policy_fabric_backend_uses_fallback_without_service_config():
    fallback = InMemoryPolicyFabricBackend()

    backend = build_policy_fabric_backend_from_config(config_from_dict({}), fallback=fallback)

    assert backend is fallback


def test_http_policy_fabric_backend_resolves_decision():
    server = _PolicyFabricHttpFixtureServer()
    try:
        backend = HttpPolicyFabricBackend(endpoint_url=server.url)

        allowed = backend.evaluate(make_event("github.pr.create"))
        missing = backend.evaluate(make_event("github.unknown"))
    finally:
        server.close()

    assert allowed is not None
    assert allowed.decision_id == "decision.allow.github.pr.create"
    assert allowed.status == ALLOW
    assert missing is None


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/decisions/github.pr.create":
            self._send(
                200,
                {
                    "decision_id": "decision.allow.github.pr.create",
                    "action": "github.pr.create",
                    "status": "allow",
                    "policy_ref": "http://policy/github-pr-create",
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


class _PolicyFabricHttpFixtureServer:
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
