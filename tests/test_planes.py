from agent_term.planes import get_plane, iter_planes


def test_sourceos_planes_include_required_integrations():
    keys = {plane.key for plane in iter_planes()}

    assert "matrix" in keys
    assert "sociosphere" in keys
    assert "prophet-workspace" in keys
    assert "slash-topics" in keys
    assert "memory-mesh" in keys
    assert "new-hope" in keys
    assert "holmes" in keys
    assert "sherlock-search" in keys
    assert "legacy-sherlock" in keys
    assert "meshrush" in keys
    assert "cloudshell-fog" in keys
    assert "agentplane" in keys
    assert "policy-fabric" in keys


def test_authority_boundaries_are_explicit():
    sociosphere = get_plane("sociosphere")
    workspace = get_plane("prophet-workspace")
    new_hope = get_plane("new-hope")
    holmes = get_plane("holmes")
    sherlock = get_plane("sherlock-search")

    assert "meta-workspace controller" in sociosphere.role
    assert "workroom" in workspace.role.lower()
    assert "semantic runtime" in new_hope.role.lower()
    assert "language intelligence fabric" in holmes.role.lower()
    assert "retrieval/search-packet" in sherlock.role


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
                "materialize_workspace",
                "hydrate_workspace_context",
                "apply_topic_membrane",
                "recall_context",
                "write_memory",
                "extract_claims",
                "apply_semantic_membrane",
                "open_casefile",
                "investigate",
                "synthesize_findings",
                "run_evals",
                "create_search_packet",
                "hydrate_context_pack",
                "username_lookup",
                "enter_graph_view",
                "diffuse_graph",
                "crystallize_artifact",
                "request_shell_session",
                "attach_pty",
                "select_executor",
                "run_bundle",
                "replay_run",
                "approve_action",
            }:
                side_effecting.append((plane.key, capability.name, capability.requires_approval))

    assert side_effecting
    assert all(required for _, _, required in side_effecting)
