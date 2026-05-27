from __future__ import annotations

import pytest

from agent_term.pre_dispatch import build_pre_dispatch_decision, validate_pre_dispatch_decision


def test_pre_dispatch_allows_resolved_non_human_with_policy_refs():
    decision = build_pre_dispatch_decision(
        decision_id="pre-dispatch:ok-001",
        requested_action="tool_use",
        participant_ref="agent://codex",
        participant_kind="agent",
        agent_registry_ref="agent-registry://codex",
        grant_refs=("grant://codex/tool-use",),
        session_ref="session://codex/001",
        revocation_state="not-revoked",
        policy_decision_refs=("policy-decision://tool-use/allow",),
        policy_status="allow",
        dispatch_target="adapter://codex",
        evidence_refs=("evidence://agent-term/pre-dispatch/ok-001",),
    )

    assert decision.dispatch_decision == "allow"
    assert decision.performed_dispatch is False
    assert decision.side_effecting is True
    validate_pre_dispatch_decision(decision)


def test_pre_dispatch_rejects_local_config_only_non_human():
    with pytest.raises(ValueError, match="Agent Registry ref"):
        build_pre_dispatch_decision(
            decision_id="pre-dispatch:local-only-invalid",
            requested_action="tool_use",
            participant_ref="agent://codex",
            participant_kind="agent",
            dispatch_target="adapter://codex",
            policy_decision_refs=("policy-decision://tool-use/allow",),
            policy_status="allow",
        )


def test_pre_dispatch_rejects_revoked_grant_dispatch():
    decision = build_pre_dispatch_decision(
        decision_id="pre-dispatch:revoked-001",
        requested_action="tool_use",
        participant_ref="agent://codex",
        participant_kind="agent",
        agent_registry_ref="agent-registry://codex",
        grant_refs=("grant://codex/tool-use",),
        session_ref="session://codex/001",
        revocation_state="revoked",
        policy_decision_refs=("policy-decision://tool-use/allow",),
        policy_status="allow",
        dispatch_target="adapter://codex",
    )

    assert decision.dispatch_decision == "deny"
    with pytest.raises(ValueError, match="revoked or unknown"):
        mutated = decision.to_dict()
        mutated["dispatch_decision"] = "allow"
        validate_pre_dispatch_decision(mutated)


def test_pre_dispatch_rejects_side_effect_without_policy_refs():
    with pytest.raises(ValueError, match="policy decision refs"):
        build_pre_dispatch_decision(
            decision_id="pre-dispatch:no-policy-invalid",
            requested_action="shell_session",
            participant_ref="human://operator",
            participant_kind="human",
            revocation_state="not-revoked",
            policy_status="allow",
            dispatch_target="adapter://shell",
        )


def test_pre_dispatch_rejects_sensitive_context_without_policy_admission():
    with pytest.raises(ValueError, match="sensitive context"):
        build_pre_dispatch_decision(
            decision_id="pre-dispatch:sensitive-invalid",
            requested_action="context_pack",
            participant_ref="human://operator",
            participant_kind="human",
            revocation_state="not-revoked",
            policy_decision_refs=("policy-decision://context/pending",),
            policy_status="pending",
            sensitive_context_requested=True,
            context_pack_refs=("context-pack://secret",),
            dispatch_target="adapter://context",
        )


def test_pre_dispatch_rejects_record_that_claims_dispatch_performed():
    decision = build_pre_dispatch_decision(
        decision_id="pre-dispatch:mutated-invalid",
        requested_action="read",
        participant_ref="human://operator",
        participant_kind="human",
        revocation_state="not-revoked",
        policy_status="allow",
        dispatch_target="adapter://noop",
    )
    payload = decision.to_dict()
    payload["performed_dispatch"] = True
    with pytest.raises(ValueError, match="must not claim dispatch"):
        validate_pre_dispatch_decision(payload)
