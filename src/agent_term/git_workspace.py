"""Git workspace state classifier for AgentTerm.

Before running any Git probe (repo-origin, branch, symbolic-ref, rev-parse,
status, or watcher commands) AgentTerm must classify the current directory into
a typed ``GitWorkspaceState``.  Expected negative states (non-repo paths, bare
repos, detached HEAD, …) must never produce warning spam; the severity-discipline
table below maps each state to the correct log level.

Runtime requirements:
- Debounce/cache stable classifications per resolved absolute path.
- Suppress repeated identical warnings.
- Never run branch commands from inside .git without first resolving the working
  tree context.
- Preserve evidence for failures that affect a user-requested operation.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# State enum
# ---------------------------------------------------------------------------


class GitWorkspaceState(str, Enum):
    """Typed classification of the current directory's Git context."""

    NOT_A_REPO = "not_a_repo"
    REPO_ROOT = "repo_root"
    INSIDE_WORKTREE = "inside_worktree"
    INSIDE_GIT_DIR = "inside_git_dir"
    BARE_REPO = "bare_repo"
    WORKTREE_NO_REMOTE = "worktree_no_remote"
    DETACHED_HEAD = "detached_head"
    CORRUPT_REPO = "corrupt_repo"
    PERMISSION_DENIED = "permission_denied"
    OPERATION_SUPERSEDED = "operation_superseded"


# ---------------------------------------------------------------------------
# Severity constants
# ---------------------------------------------------------------------------

SEVERITY_DEBUG: Final = "debug"
SEVERITY_INFO: Final = "info"
SEVERITY_WARNING: Final = "warning"
SEVERITY_ERROR: Final = "error"

# Remote status constants
REMOTE_AVAILABLE: Final = "available"
REMOTE_MISSING: Final = "missing"
REMOTE_NOT_APPLICABLE: Final = "not-applicable"
REMOTE_ERROR: Final = "error"

# Default severity for each state (passive / no user-requested operation)
_DEFAULT_SEVERITY: dict[GitWorkspaceState, str] = {
    GitWorkspaceState.NOT_A_REPO: SEVERITY_INFO,
    GitWorkspaceState.REPO_ROOT: SEVERITY_INFO,
    GitWorkspaceState.INSIDE_WORKTREE: SEVERITY_INFO,
    GitWorkspaceState.INSIDE_GIT_DIR: SEVERITY_INFO,
    GitWorkspaceState.BARE_REPO: SEVERITY_INFO,
    GitWorkspaceState.WORKTREE_NO_REMOTE: SEVERITY_INFO,
    GitWorkspaceState.DETACHED_HEAD: SEVERITY_INFO,
    GitWorkspaceState.CORRUPT_REPO: SEVERITY_WARNING,
    GitWorkspaceState.PERMISSION_DENIED: SEVERITY_WARNING,
    GitWorkspaceState.OPERATION_SUPERSEDED: SEVERITY_DEBUG,
}


def severity_for_state(
    state: GitWorkspaceState,
    *,
    operation_requires_remote: bool = False,
    operation_requires_worktree: bool = False,
    operation_requires_branch: bool = False,
) -> str:
    """Return the appropriate severity for *state* given the requested operation.

    Args:
        state: The classified workspace state.
        operation_requires_remote: True when the pending operation needs a remote
            (e.g. ``git fetch``, ``git push``).
        operation_requires_worktree: True when the pending operation needs a full
            worktree (not applicable inside bare repos or ``.git`` directories).
        operation_requires_branch: True when the pending operation requires a
            resolved branch reference (not applicable for detached HEAD).
    """
    if state == GitWorkspaceState.WORKTREE_NO_REMOTE and operation_requires_remote:
        return SEVERITY_WARNING
    if state == GitWorkspaceState.INSIDE_GIT_DIR and operation_requires_worktree:
        return SEVERITY_WARNING
    if state == GitWorkspaceState.BARE_REPO and operation_requires_worktree:
        return SEVERITY_WARNING
    if state == GitWorkspaceState.DETACHED_HEAD and operation_requires_branch:
        return SEVERITY_WARNING
    return _DEFAULT_SEVERITY[state]


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GitWorkspaceClassification:
    """Full classification of a directory's Git workspace context.

    Attributes:
        state: The typed ``GitWorkspaceState``.
        path: The resolved absolute path that was classified.
        branch: Branch name, ``"detached"``, ``"unknown"``, or
            ``"not-applicable"``.
        remote_status: ``"available"``, ``"missing"``, ``"not-applicable"``,
            or ``"error"``.
        severity: Default severity for passive probes of this state.
        action_hint: Optional remediation hint for the operator.
        metadata: Adapter-style pass-through metadata for event emission.
    """

    state: GitWorkspaceState
    path: str
    branch: str = "unknown"
    remote_status: str = REMOTE_NOT_APPLICABLE
    severity: str = SEVERITY_INFO
    action_hint: str = "none"
    metadata: dict[str, object] = field(default_factory=dict)

    def to_status_line(self) -> str:
        """Render compact workspace health for the terminal UI/status line."""
        return (
            f"Workspace: {self.path}\n"
            f"Git state: {self.state.value}\n"
            f"Remote: {self.remote_status}\n"
            f"Branch: {self.branch}\n"
            f"Severity: {self.severity}\n"
            f"Action: {self.action_hint}"
        )

    def to_metadata(self) -> dict[str, object]:
        return {
            "git_state": self.state.value,
            "git_path": self.path,
            "git_branch": self.branch,
            "git_remote_status": self.remote_status,
            "git_severity": self.severity,
            "git_action_hint": self.action_hint,
            **self.metadata,
        }


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

# Module-level classification cache: resolved_path -> GitWorkspaceClassification
_CLASSIFICATION_CACHE: dict[str, GitWorkspaceClassification] = {}


def classify_git_workspace(
    path: str | Path | None = None,
    *,
    force: bool = False,
) -> GitWorkspaceClassification:
    """Classify the Git workspace state for *path* (defaults to ``cwd``).

    Results are cached by resolved absolute path so repeated passive probes
    (e.g. watcher ticks) do not spawn redundant subprocesses.  Pass
    ``force=True`` to bypass the cache (useful after a ``git init`` or
    ``git clone``).

    Args:
        path: Directory to classify.  Defaults to the current working directory.
        force: Bypass the in-process classification cache.
    """
    resolved = str(Path(path or Path.cwd()).resolve())

    if not force and resolved in _CLASSIFICATION_CACHE:
        return _CLASSIFICATION_CACHE[resolved]

    classification = _do_classify(resolved)
    _CLASSIFICATION_CACHE[resolved] = classification
    return classification


def clear_classification_cache() -> None:
    """Clear the in-process classification cache (test helper and reload hook)."""
    _CLASSIFICATION_CACHE.clear()


# ---------------------------------------------------------------------------
# Internal classification logic
# ---------------------------------------------------------------------------


def _run_git(args: list[str], cwd: str) -> tuple[int, str, str]:
    """Run a git sub-command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except PermissionError as exc:
        return -1, "", str(exc)
    except FileNotFoundError:
        # git binary not on PATH - treat the same as not_a_repo for safety
        return 128, "", "git not found"
    except subprocess.TimeoutExpired:
        return -2, "", "timeout"


def _do_classify(resolved_path: str) -> GitWorkspaceClassification:  # noqa: PLR0911 (many return paths)
    """Perform the actual filesystem + subprocess classification."""

    # 1. Permission check before any Git probe
    try:
        os.listdir(resolved_path)
    except PermissionError as exc:
        return GitWorkspaceClassification(
            state=GitWorkspaceState.PERMISSION_DENIED,
            path=resolved_path,
            severity=SEVERITY_WARNING,
            action_hint="Check directory permissions.",
            metadata={"permission_error": str(exc)},
        )
    except FileNotFoundError:
        return GitWorkspaceClassification(
            state=GitWorkspaceState.NOT_A_REPO,
            path=resolved_path,
            severity=SEVERITY_INFO,
            action_hint="none",
        )

    # 2. Detect .git directory probing early so we never accidentally run
    #    branch commands without resolving the worktree context first.
    path_obj = Path(resolved_path)
    if path_obj.name == ".git" or any(p.name == ".git" and p.is_dir() for p in path_obj.parents):
        # Check whether we are *inside* a .git directory
        rc, inside_git, _ = _run_git(["rev-parse", "--is-inside-git-dir"], resolved_path)
        if rc == 0 and inside_git == "true":
            return GitWorkspaceClassification(
                state=GitWorkspaceState.INSIDE_GIT_DIR,
                path=resolved_path,
                severity=SEVERITY_INFO,
                action_hint="Switch to the worktree root before running branch commands.",
            )

    # 3. Ask Git whether this is a valid repository at all.
    #    --is-inside-work-tree returns "true" for normal worktrees,
    #    --is-bare-repository returns "true" for bare repos.
    rc_wt, inside_wt, stderr_wt = _run_git(
        ["rev-parse", "--is-inside-work-tree"], resolved_path
    )

    if rc_wt != 0:
        # Non-zero exit from rev-parse almost always means not a repo.
        stderr_lower = stderr_wt.lower()
        if "permission denied" in stderr_lower:
            return GitWorkspaceClassification(
                state=GitWorkspaceState.PERMISSION_DENIED,
                path=resolved_path,
                severity=SEVERITY_WARNING,
                action_hint="Check Git directory permissions.",
                metadata={"git_stderr": stderr_wt},
            )
        if "corrupt" in stderr_lower or "bad object" in stderr_lower or "not a valid" in stderr_lower:
            return GitWorkspaceClassification(
                state=GitWorkspaceState.CORRUPT_REPO,
                path=resolved_path,
                severity=SEVERITY_WARNING,
                action_hint="Run `git fsck` to inspect and repair the repository.",
                metadata={"git_stderr": stderr_wt},
            )
        # Expected: not a git repository
        return GitWorkspaceClassification(
            state=GitWorkspaceState.NOT_A_REPO,
            path=resolved_path,
            severity=SEVERITY_INFO,
            action_hint="none",
        )

    # 4. We are inside a Git repository of some kind.
    if inside_wt == "false":
        # Inside .git dir (rev-parse agrees)
        return GitWorkspaceClassification(
            state=GitWorkspaceState.INSIDE_GIT_DIR,
            path=resolved_path,
            severity=SEVERITY_INFO,
            action_hint="Switch to the worktree root before running branch commands.",
        )

    # 5. Check for bare repository
    rc_bare, is_bare, _ = _run_git(["rev-parse", "--is-bare-repository"], resolved_path)
    if rc_bare == 0 and is_bare == "true":
        return GitWorkspaceClassification(
            state=GitWorkspaceState.BARE_REPO,
            path=resolved_path,
            remote_status=_probe_remote(resolved_path),
            severity=SEVERITY_INFO,
            action_hint="none",
        )

    # 6. Determine whether we are at the repo root or inside a worktree subdirectory.
    rc_top, toplevel, _ = _run_git(["rev-parse", "--show-toplevel"], resolved_path)
    if rc_top != 0:
        # Unexpected failure after we already confirmed inside-work-tree
        return GitWorkspaceClassification(
            state=GitWorkspaceState.CORRUPT_REPO,
            path=resolved_path,
            severity=SEVERITY_WARNING,
            action_hint="Run `git fsck` to inspect and repair the repository.",
        )

    at_root = Path(toplevel).resolve() == Path(resolved_path).resolve()
    state_candidate = (
        GitWorkspaceState.REPO_ROOT if at_root else GitWorkspaceState.INSIDE_WORKTREE
    )

    # 7. Probe branch / HEAD
    branch, is_detached = _probe_branch(resolved_path)
    if is_detached:
        return GitWorkspaceClassification(
            state=GitWorkspaceState.DETACHED_HEAD,
            path=resolved_path,
            branch="detached",
            remote_status=_probe_remote(resolved_path),
            severity=SEVERITY_INFO,
            action_hint="Run `git checkout <branch>` to reattach HEAD.",
        )

    # 8. Probe remote
    remote_status = _probe_remote(resolved_path)
    if remote_status == REMOTE_MISSING:
        return GitWorkspaceClassification(
            state=GitWorkspaceState.WORKTREE_NO_REMOTE,
            path=resolved_path,
            branch=branch,
            remote_status=REMOTE_MISSING,
            severity=SEVERITY_INFO,
            action_hint="Run `git remote add origin <url>` to add a remote.",
        )

    return GitWorkspaceClassification(
        state=state_candidate,
        path=resolved_path,
        branch=branch,
        remote_status=remote_status,
        severity=SEVERITY_INFO,
        action_hint="none",
    )


def _probe_branch(cwd: str) -> tuple[str, bool]:
    """Return (branch_name_or_sentinel, is_detached).

    Uses ``git symbolic-ref HEAD`` which exits non-zero for detached HEAD.
    """
    rc, ref, _ = _run_git(["symbolic-ref", "--short", "HEAD"], cwd)
    if rc == 0 and ref:
        return ref, False
    # Detached HEAD or symbolic-ref unavailable
    rc2, sha, _ = _run_git(["rev-parse", "--short", "HEAD"], cwd)
    if rc2 == 0 and sha:
        return sha, True
    return "unknown", False


def _probe_remote(cwd: str) -> str:
    """Return a remote status string for the current repo."""
    rc, remotes, stderr = _run_git(["remote"], cwd)
    if rc != 0:
        return REMOTE_ERROR
    if remotes:
        return REMOTE_AVAILABLE
    return REMOTE_MISSING
