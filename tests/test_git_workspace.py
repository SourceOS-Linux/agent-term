"""Tests for the GitWorkspaceState classifier.

All Git operations are faked via monkeypatching ``_run_git`` so the tests run
without a real Git installation and without touching the filesystem beyond what
``tmp_path`` gives us.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_term.git_workspace import (
    REMOTE_AVAILABLE,
    REMOTE_MISSING,
    SEVERITY_DEBUG,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    GitWorkspaceClassification,
    GitWorkspaceState,
    classify_git_workspace,
    clear_classification_cache,
    severity_for_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_git(responses: dict[tuple[str, ...], tuple[int, str, str]]):
    """Return a _run_git replacement that uses a fixed response table.

    Keys are tuples of the extra git args (everything after "git").
    """

    def _run(args: list[str], cwd: str) -> tuple[int, str, str]:
        key = tuple(args)
        if key in responses:
            return responses[key]
        # Fallback: unknown command → fail
        return 128, "", "not stubbed"

    return _run


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure the classification cache does not leak between tests."""
    clear_classification_cache()
    yield
    clear_classification_cache()


# ---------------------------------------------------------------------------
# not_a_repo
# ---------------------------------------------------------------------------


def test_not_a_repo_for_plain_directory(tmp_path: Path):
    """A non-repo directory must be classified as not_a_repo at info severity."""
    responses = {
        ("rev-parse", "--is-inside-work-tree"): (128, "", "not a git repository"),
    }
    with patch("agent_term.git_workspace._run_git", side_effect=_fake_git(responses)):
        result = classify_git_workspace(tmp_path)

    assert result.state == GitWorkspaceState.NOT_A_REPO
    assert result.severity == SEVERITY_INFO
    assert result.action_hint == "none"


def test_not_a_repo_does_not_emit_warning(tmp_path: Path):
    """Passive discovery of a non-repo must stay at info, never warning."""
    responses = {
        ("rev-parse", "--is-inside-work-tree"): (128, "", "not a git repository"),
    }
    with patch("agent_term.git_workspace._run_git", side_effect=_fake_git(responses)):
        result = classify_git_workspace(tmp_path)

    assert result.severity != SEVERITY_WARNING


# ---------------------------------------------------------------------------
# repo_root
# ---------------------------------------------------------------------------


def test_repo_root_classification(tmp_path: Path):
    """A repo root directory is classified as repo_root with a resolved branch."""
    responses = {
        ("rev-parse", "--is-inside-work-tree"): (0, "true", ""),
        ("rev-parse", "--is-bare-repository"): (0, "false", ""),
        ("rev-parse", "--show-toplevel"): (0, str(tmp_path), ""),
        ("symbolic-ref", "--short", "HEAD"): (0, "main", ""),
        ("remote",): (0, "origin", ""),
    }
    with patch("agent_term.git_workspace._run_git", side_effect=_fake_git(responses)):
        result = classify_git_workspace(tmp_path)

    assert result.state == GitWorkspaceState.REPO_ROOT
    assert result.branch == "main"
    assert result.remote_status == REMOTE_AVAILABLE
    assert result.severity == SEVERITY_INFO


# ---------------------------------------------------------------------------
# inside_worktree
# ---------------------------------------------------------------------------


def test_inside_worktree_classification(tmp_path: Path):
    """A subdirectory of a repo is classified as inside_worktree."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subdir = repo_root / "src"
    subdir.mkdir()

    responses = {
        ("rev-parse", "--is-inside-work-tree"): (0, "true", ""),
        ("rev-parse", "--is-bare-repository"): (0, "false", ""),
        ("rev-parse", "--show-toplevel"): (0, str(repo_root), ""),
        ("symbolic-ref", "--short", "HEAD"): (0, "feature/x", ""),
        ("remote",): (0, "origin", ""),
    }
    with patch("agent_term.git_workspace._run_git", side_effect=_fake_git(responses)):
        result = classify_git_workspace(subdir)

    assert result.state == GitWorkspaceState.INSIDE_WORKTREE
    assert result.branch == "feature/x"
    assert result.severity == SEVERITY_INFO


# ---------------------------------------------------------------------------
# inside_git_dir
# ---------------------------------------------------------------------------


def test_inside_git_dir_classification(tmp_path: Path):
    """Probing inside a .git directory is classified and not treated as failure."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    responses = {
        ("rev-parse", "--is-inside-git-dir"): (0, "true", ""),
        ("rev-parse", "--is-inside-work-tree"): (0, "false", ""),
        ("rev-parse", "--is-bare-repository"): (0, "false", ""),
        ("rev-parse", "--show-toplevel"): (0, str(tmp_path), ""),
        ("symbolic-ref", "--short", "HEAD"): (0, "main", ""),
        ("remote",): (0, "origin", ""),
    }
    with patch("agent_term.git_workspace._run_git", side_effect=_fake_git(responses)):
        result = classify_git_workspace(git_dir)

    assert result.state == GitWorkspaceState.INSIDE_GIT_DIR
    assert result.severity == SEVERITY_INFO
    assert "worktree" in result.action_hint.lower()


def test_inside_git_dir_worktree_operation_elevates_to_warning(tmp_path: Path):
    """inside_git_dir severity escalates to warning when a worktree op is requested."""
    result = severity_for_state(
        GitWorkspaceState.INSIDE_GIT_DIR,
        operation_requires_worktree=True,
    )
    assert result == SEVERITY_WARNING


# ---------------------------------------------------------------------------
# bare_repo
# ---------------------------------------------------------------------------


def test_bare_repo_classification(tmp_path: Path):
    """A bare repository is classified as bare_repo at info severity."""
    responses = {
        ("rev-parse", "--is-inside-work-tree"): (0, "true", ""),
        ("rev-parse", "--is-bare-repository"): (0, "true", ""),
        ("remote",): (0, "origin", ""),
    }
    with patch("agent_term.git_workspace._run_git", side_effect=_fake_git(responses)):
        result = classify_git_workspace(tmp_path)

    assert result.state == GitWorkspaceState.BARE_REPO
    assert result.severity == SEVERITY_INFO


def test_bare_repo_worktree_operation_elevates_severity():
    """bare_repo severity escalates to warning when a worktree op is requested."""
    result = severity_for_state(
        GitWorkspaceState.BARE_REPO,
        operation_requires_worktree=True,
    )
    assert result == SEVERITY_WARNING


# ---------------------------------------------------------------------------
# worktree_no_remote
# ---------------------------------------------------------------------------


def test_worktree_no_remote_classification(tmp_path: Path):
    """A repo without a configured remote is classified as worktree_no_remote."""
    responses = {
        ("rev-parse", "--is-inside-work-tree"): (0, "true", ""),
        ("rev-parse", "--is-bare-repository"): (0, "false", ""),
        ("rev-parse", "--show-toplevel"): (0, str(tmp_path), ""),
        ("symbolic-ref", "--short", "HEAD"): (0, "main", ""),
        ("remote",): (0, "", ""),
    }
    with patch("agent_term.git_workspace._run_git", side_effect=_fake_git(responses)):
        result = classify_git_workspace(tmp_path)

    assert result.state == GitWorkspaceState.WORKTREE_NO_REMOTE
    assert result.remote_status == REMOTE_MISSING
    assert result.severity == SEVERITY_INFO


def test_worktree_no_remote_remote_op_elevates_severity():
    """worktree_no_remote escalates to warning when a remote op is requested."""
    result = severity_for_state(
        GitWorkspaceState.WORKTREE_NO_REMOTE,
        operation_requires_remote=True,
    )
    assert result == SEVERITY_WARNING


# ---------------------------------------------------------------------------
# detached_head
# ---------------------------------------------------------------------------


def test_detached_head_classification(tmp_path: Path):
    """A detached HEAD is classified as detached_head at info severity."""
    responses = {
        ("rev-parse", "--is-inside-work-tree"): (0, "true", ""),
        ("rev-parse", "--is-bare-repository"): (0, "false", ""),
        ("rev-parse", "--show-toplevel"): (0, str(tmp_path), ""),
        ("symbolic-ref", "--short", "HEAD"): (1, "", "HEAD detached"),
        ("rev-parse", "--short", "HEAD"): (0, "abc1234", ""),
        ("remote",): (0, "origin", ""),
    }
    with patch("agent_term.git_workspace._run_git", side_effect=_fake_git(responses)):
        result = classify_git_workspace(tmp_path)

    assert result.state == GitWorkspaceState.DETACHED_HEAD
    assert result.branch == "detached"
    assert result.severity == SEVERITY_INFO
    assert "checkout" in result.action_hint.lower()


def test_detached_head_branch_op_elevates_severity():
    """detached_head escalates to warning when an op requiring a branch is requested."""
    result = severity_for_state(
        GitWorkspaceState.DETACHED_HEAD,
        operation_requires_branch=True,
    )
    assert result == SEVERITY_WARNING


# ---------------------------------------------------------------------------
# corrupt_repo
# ---------------------------------------------------------------------------


def test_corrupt_repo_classification(tmp_path: Path):
    """A corrupt repository emits warning severity."""
    responses = {
        ("rev-parse", "--is-inside-work-tree"): (
            128,
            "",
            "error: object file .git/objects/xx is not a valid object",
        ),
    }
    with patch("agent_term.git_workspace._run_git", side_effect=_fake_git(responses)):
        result = classify_git_workspace(tmp_path)

    assert result.state == GitWorkspaceState.CORRUPT_REPO
    assert result.severity == SEVERITY_WARNING
    assert "fsck" in result.action_hint.lower()


# ---------------------------------------------------------------------------
# permission_denied
# ---------------------------------------------------------------------------


def test_permission_denied_classification(tmp_path: Path):
    """A directory with denied access is classified as permission_denied at warning."""
    responses = {
        ("rev-parse", "--is-inside-work-tree"): (
            128,
            "",
            "fatal: permission denied: .git/config",
        ),
    }
    with patch("agent_term.git_workspace._run_git", side_effect=_fake_git(responses)):
        result = classify_git_workspace(tmp_path)

    assert result.state == GitWorkspaceState.PERMISSION_DENIED
    assert result.severity == SEVERITY_WARNING


def test_permission_denied_via_os_listdir(tmp_path: Path):
    """PermissionError from os.listdir must be classified as permission_denied."""
    with patch("agent_term.git_workspace.os.listdir", side_effect=PermissionError("denied")):
        result = classify_git_workspace(tmp_path)

    assert result.state == GitWorkspaceState.PERMISSION_DENIED
    assert result.severity == SEVERITY_WARNING


# ---------------------------------------------------------------------------
# operation_superseded
# ---------------------------------------------------------------------------


def test_operation_superseded_is_debug_severity():
    """Superseded watcher commands must be debug/trace, never user-visible warnings."""
    result = severity_for_state(GitWorkspaceState.OPERATION_SUPERSEDED)
    assert result == SEVERITY_DEBUG


# ---------------------------------------------------------------------------
# Debounce / cache
# ---------------------------------------------------------------------------


def test_classification_is_cached_for_same_path(tmp_path: Path):
    """Repeated classify calls for the same path reuse the cached result."""
    call_count = 0

    def _counting_run(args: list[str], cwd: str) -> tuple[int, str, str]:
        nonlocal call_count
        call_count += 1
        return 128, "", "not a git repository"

    with patch("agent_term.git_workspace._run_git", side_effect=_counting_run):
        r1 = classify_git_workspace(tmp_path)
        r2 = classify_git_workspace(tmp_path)

    assert r1 is r2
    # _run_git should have been called only for the first classify
    assert call_count == 1


def test_force_bypasses_cache(tmp_path: Path):
    """force=True must bypass the cache and re-classify."""
    call_count = 0

    def _counting_run(args: list[str], cwd: str) -> tuple[int, str, str]:
        nonlocal call_count
        call_count += 1
        return 128, "", "not a git repository"

    with patch("agent_term.git_workspace._run_git", side_effect=_counting_run):
        classify_git_workspace(tmp_path)
        classify_git_workspace(tmp_path, force=True)

    assert call_count == 2


# ---------------------------------------------------------------------------
# Status line / to_metadata
# ---------------------------------------------------------------------------


def test_status_line_contains_all_fields():
    """to_status_line() must expose all required UX fields."""
    clf = GitWorkspaceClassification(
        state=GitWorkspaceState.REPO_ROOT,
        path="/tmp/repo",
        branch="main",
        remote_status=REMOTE_AVAILABLE,
        severity=SEVERITY_INFO,
        action_hint="none",
    )
    line = clf.to_status_line()
    assert "Workspace:" in line
    assert "Git state:" in line
    assert "Remote:" in line
    assert "Branch:" in line
    assert "Severity:" in line
    assert "Action:" in line


def test_to_metadata_contains_all_keys():
    clf = GitWorkspaceClassification(
        state=GitWorkspaceState.WORKTREE_NO_REMOTE,
        path="/tmp/repo",
        branch="dev",
        remote_status=REMOTE_MISSING,
        severity=SEVERITY_INFO,
        action_hint="add a remote",
    )
    md = clf.to_metadata()
    assert md["git_state"] == "worktree_no_remote"
    assert md["git_branch"] == "dev"
    assert md["git_remote_status"] == REMOTE_MISSING
    assert md["git_severity"] == SEVERITY_INFO
    assert md["git_action_hint"] == "add a remote"


# ---------------------------------------------------------------------------
# Severity discipline invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "state",
    [
        GitWorkspaceState.NOT_A_REPO,
        GitWorkspaceState.INSIDE_GIT_DIR,
        GitWorkspaceState.WORKTREE_NO_REMOTE,
        GitWorkspaceState.DETACHED_HEAD,
        GitWorkspaceState.BARE_REPO,
    ],
)
def test_passive_states_are_never_warning_or_error(state: GitWorkspaceState):
    """Passive discovery of expected negative states must not produce warnings."""
    result = severity_for_state(state)
    assert result not in {SEVERITY_WARNING, "error"}, (
        f"{state.value} passive severity must be info or debug, got {result!r}"
    )


def test_corrupt_repo_default_severity_is_warning():
    assert severity_for_state(GitWorkspaceState.CORRUPT_REPO) == SEVERITY_WARNING


def test_permission_denied_default_severity_is_warning():
    assert severity_for_state(GitWorkspaceState.PERMISSION_DENIED) == SEVERITY_WARNING
