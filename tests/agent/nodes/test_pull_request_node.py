"""Tests for the pull_request node."""

from unittest.mock import Mock

import pytest

from app.agent.models.node_results import GitOperationResult
from app.agent.nodes import pull_request as pr_module


@pytest.fixture
def base_state():
    """Provide a default agent state structure."""
    return {
        "agent_summary": ["Initial summary"],
        "task_id": "task-123",
    }


def _setup_success_path(monkeypatch):
    """Set default happy-path patches for git operations."""

    monkeypatch.setattr(
        pr_module, "check_git_status",
        lambda: GitOperationResult(success=True, message="Changes detected")
    )
    monkeypatch.setattr(
        pr_module, "git_add_all",
        lambda: GitOperationResult(success=True, message="All changes staged")
    )
    monkeypatch.setattr(
        pr_module, "git_commit",
        lambda message: GitOperationResult(success=True, message="Committed")
    )
    monkeypatch.setattr(
        pr_module, "git_push",
        lambda: GitOperationResult(success=True, message="pushed")
    )
    monkeypatch.setattr(pr_module, "_build_pr_inputs", lambda state: ("Title", "Body"))


def test_create_or_update_pr_success(monkeypatch, base_state):
    """Ensure successful PR creation appends a summary entry and stores PR info."""

    _setup_success_path(monkeypatch)
    pr_url = "https://github.com/foo/bar/pull/42"
    monkeypatch.setattr(
        pr_module,
        "create_or_update_pr",
        lambda title, body: (True, "done", pr_url),
    )

    update_mock = Mock()
    monkeypatch.setattr(pr_module, "update_task_pr_info", update_mock)

    success, summaries = pr_module._create_or_update_pr(base_state.copy())  # pylint: disable=protected-access

    assert success is True
    assert summaries[-1] == f"**[Pr]** Pull request available at\n\n {pr_url}"
    update_mock.assert_called_once_with("task-123", 42, pr_url)


def test_create_or_update_pr_no_changes(monkeypatch, base_state):
    """Ensure failure path appends descriptive summary when no changes exist."""

    monkeypatch.setattr(
        pr_module, "check_git_status",
        lambda: GitOperationResult(success=False, message="No changes detected")
    )

    success, summaries = pr_module._create_or_update_pr(base_state.copy())  # pylint: disable=protected-access

    assert success is False
    assert summaries[-1] == "**[Pr]** Pull request skipped: no changes detected"


def test_create_or_update_pr_push_failure(monkeypatch, base_state):
    """Git push failure should append summary describing the error."""

    _setup_success_path(monkeypatch)
    monkeypatch.setattr(
        pr_module, "git_push",
        lambda: GitOperationResult(success=False, message="remote rejected")
    )

    success, summaries = pr_module._create_or_update_pr(base_state.copy())  # pylint: disable=protected-access

    assert success is False
    assert (
        summaries[-1]
        == "**[Pr]** Pull request failed: remote rejected"
    )


def test_create_or_update_pr_api_failure(monkeypatch, base_state):
    """GitHub API failure should record summary entry."""

    _setup_success_path(monkeypatch)
    monkeypatch.setattr(
        pr_module,
        "create_or_update_pr",
        lambda title, body: (False, "validation failed", None),
    )

    success, summaries = pr_module._create_or_update_pr(base_state.copy())  # pylint: disable=protected-access

    assert success is False
    assert (
        summaries[-1]
        == "**[Pr]** Pull request creation/update failed: validation failed"
    )


def test_create_or_update_pr_missing_url(monkeypatch, base_state):
    """Missing PR URL after success should add warning summary and return failure."""

    _setup_success_path(monkeypatch)
    monkeypatch.setattr(
        pr_module,
        "create_or_update_pr",
        lambda title, body: (True, "done", None),
    )

    success, summaries = pr_module._create_or_update_pr(base_state.copy())  # pylint: disable=protected-access

    assert success is False
    assert summaries[-1] == "**[Pr]** Pull request missing URL despite success"


def test_generate_commit_message_uses_task_role_prefix():
    """Commit message should align with router-provided role."""

    state = {
        "agent_summary": ["**[Coder]** Implement feature X"],
        "task_role": "coder",
    }

    message = pr_module._generate_commit_message(state)  # pylint: disable=protected-access

    assert message == "feat: Implement feature X"


def test_generate_commit_message_falls_back_when_summary_missing():
    """Fallback commit message should be used when summaries absent or empty."""

    state = {"agent_summary": []}

    message = pr_module._generate_commit_message(state)  # pylint: disable=protected-access

    assert message == "fix: automated test-driven changes"


def test_generate_commit_message_trims_summary_prefix_and_length():
    """Role prefix is removed while preserving content and enforcing max length."""

    long_summary = "**[Bugfixer]** " + "x" * 100
    state = {"agent_summary": [long_summary], "task_role": "bugfixer"}

    message = pr_module._generate_commit_message(state)  # pylint: disable=protected-access

    assert message.startswith("fix: ")
    assert len(message) <= 75  # prefix plus ellipsis trimming


def test_generate_commit_message_ignores_tester_summaries():
    """Tester entries should be skipped when composing commit messages."""

    state = {
        "agent_summary": [
            "**[Tester]** Confirmed all tests pass",
            "**[Bugfixer]** Fixed broken import",
        ],
        "task_role": "bugfixer",
    }

    message = pr_module._generate_commit_message(state)  # pylint: disable=protected-access

    assert message == "fix: Fixed broken import"
