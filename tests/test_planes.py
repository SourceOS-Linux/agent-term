from agent_term.planes import get_plane, iter_planes


def test_sourceos_planes_include_required_integrations():
    keys = {plane.key for plane in iter_planes()}

    assert "matrix" in keys
    assert "cloudshell-fog" in keys
    assert "agentplane" in keys
    assert "policy-fabric" in keys
    assert "sherlock-search" in keys
    assert "legacy-sherlock" in keys


def test_sherlock_search_is_preferred_surface():
    sherlock = get_plane("sherlock-search")
    legacy = get_plane("legacy-sherlock")

    assert sherlock.repository == "SocioProphet/sherlock-search"
    assert "preferred" in " ".join(sherlock.notes).lower()
    assert legacy.repository == "SocioProphet/sherlock"
    assert any("policy-gated" in note for note in legacy.notes)


def test_side_effecting_capabilities_require_approval():
    side_effecting = []
    for plane in iter_planes():
        for capability in plane.capabilities:
            if capability.name in {
                "room_event_emit",
                "request_shell_session",
                "attach_pty",
                "select_executor",
                "run_bundle",
                "replay_run",
                "approve_action",
                "create_search_packet",
                "hydrate_context_pack",
                "username_lookup",
            }:
                side_effecting.append((plane.key, capability.name, capability.requires_approval))

    assert side_effecting
    assert all(required for _, _, required in side_effecting)
