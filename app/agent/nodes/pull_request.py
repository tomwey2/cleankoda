"""Create a pull request node"""

import logging
from typing import Any, Dict

from app.agent.services.git_operations import (
    check_git_status,
    git_add_all,
    git_commit,
    git_push,
)
from app.agent.services.summaries import (
    append_agent_summary,
    build_agent_summary_markdown,
)
from app.agent.services.pull_request import create_or_update_pr
from app.agent.state import AgentState
from app.core.task_repository import update_task_pr_info

logger = logging.getLogger(__name__)


def create_pull_request_node():
    """Create a pull request node"""

    async def pull_request_node(state: AgentState) -> Dict[str, Any]:
        success, summary_entries = _create_or_update_pr(state)
        if success:
            logger.info("Pull request created/updated successfully")
        else:
            logger.error("Pull request creation/update failed")

        return {"agent_summary": summary_entries, "current_node": "pull_request"}

    return pull_request_node


def _create_or_update_pr(state: AgentState):
    summary_entries = list(state.get("agent_summary") or [])

    # Check for changes
    status_result = check_git_status()
    if not status_result.success:
        logger.info("No changes detected, skipping Git workflow")
        failure_reason = "Pull request skipped: no changes detected"
        summary_entries = _append_summary(summary_entries, state, "PR", failure_reason)
        return False, summary_entries

    # Execute git operations
    git_error = _execute_git_operations(state)
    if git_error:
        summary_entries = _append_summary(summary_entries, state, "PR", git_error)
        return False, summary_entries

    # Create or update PR
    pr_result = _handle_pr_creation(state)
    if not pr_result[0]:
        summary_entries = _append_summary(summary_entries, state, "PR", pr_result[1])
        return False, summary_entries

    pr_url = pr_result[1]
    task_id = state.get("task_id")
    if task_id and pr_url:
        pr_number = _extract_pr_number_from_url(pr_url)
        if pr_number:
            update_task_pr_info(task_id, pr_number, pr_url)
            logger.info("Stored PR #%d for task %s", pr_number, task_id)

    summary_entries = _append_summary(
        summary_entries,
        state,
        "PR",
        f"Pull request available at\n\n {pr_url}",
    )
    return True, summary_entries

def _append_summary(
    summary_entries: list[str], state: AgentState, title: str, message: str
) -> list[str]:
    summary_entries = append_agent_summary(summary_entries, title, message)
    state["agent_summary"] = summary_entries
    return summary_entries


def _execute_git_operations(state: AgentState) -> str | None:
    """Execute git add, commit, and push. Returns error message or None."""
    add_result = git_add_all()
    if not add_result.success:
        logger.error("Git add failed: %s", add_result.message)
        return f"Pull request failed: {add_result.message}"

    commit_message = _generate_commit_message(state)
    commit_result = git_commit(commit_message)
    if not commit_result.success:
        logger.error("Git commit failed: %s", commit_result.message)
        return f"Pull request failed: {commit_result.message}"

    push_result = git_push()
    if not push_result.success:
        logger.error("Git push failed: %s", push_result.message)
        return f"Pull request failed: {push_result.message}"

    return None


def _generate_commit_message(state: AgentState) -> str:
    """Generate a concise commit message from the latest agent summary."""
    summaries = state.get("agent_summary") or []
    summary_text = ""
    summary_role: str | None = None

    for entry in reversed(summaries):
        role, text = _parse_summary_entry(entry)
        if (role or "").lower() == "tester":
            continue
        cleaned_text = text.strip()
        if cleaned_text:
            summary_text = cleaned_text
            summary_role = role
            break

    if not summary_text:
        return "fix: automated test-driven changes"

    prefix_map = {
        "coder": "feat",
        "bugfixer": "fix",
        "analyst": "chore",
    }
    role = (summary_role or state.get("task_role") or "").strip().lower()
    prefix = prefix_map.get(role, "chore")

    summary_text = f"{prefix}: {summary_text}"
    if len(summary_text) > 75:
        summary_text = summary_text[:72].rstrip() + "..."

    return summary_text


def _parse_summary_entry(entry: str) -> tuple[str | None, str]:
    """Return (role, summary_text) from a formatted summary entry."""
    if not entry:
        return None, ""

    trimmed = entry.strip()
    if trimmed.startswith("**["):
        closing = trimmed.find("]**")
        if closing != -1:
            role = trimmed[3:closing].strip() or None
            summary_text = trimmed[closing + 3 :].strip()
            return (role.lower() if role else None), summary_text

    return None, trimmed


def _handle_pr_creation(state: AgentState) -> tuple[bool, str]:
    """Create or update PR. Returns (success, url_or_error_message)."""
    pr_title, pr_body = _build_pr_inputs(state)
    pr_success, pr_msg, pr_url = create_or_update_pr(
        title=pr_title,
        body=pr_body,
    )

    if not pr_success:
        logger.error("PR creation/update failed: %s", pr_msg)
        return False, f"Pull request creation/update failed: {pr_msg}"

    logger.info("Git workflow completed successfully: %s", pr_msg)
    if not pr_url:
        logger.warning("PR creation succeeded but no URL was returned")
        return False, "Pull request missing URL despite success"

    return True, pr_url


def _extract_pr_number_from_url(pr_url: str) -> int | None:
    """
    Extract the PR number from a GitHub PR URL.

    Args:
        pr_url: GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)

    Returns:
        The PR number, or None if extraction fails
    """
    try:
        parts = pr_url.rstrip("/").split("/")
        if len(parts) >= 2 and parts[-2] == "pull":
            return int(parts[-1])
    except (ValueError, IndexError):
        pass
    return None


def _build_pr_inputs(state: AgentState) -> tuple[str, str]:
    """
    Build the PR title and body using the task name and agent summaries.
    """
    aggregated_summary = build_agent_summary_markdown(
        state,
        heading="## Agent Update",
        bullet_prefix="- ",
        line_separator="\n",
    )
    pr_body_summary = aggregated_summary
    task_title = state.get("task").name if state.get("task") else ""
    pr_title = task_title or "Automated Fix"
    pr_body = "Automated changes after successful tests."
    if pr_body_summary:
        pr_body += f"\n\n{pr_body_summary}"

    return pr_title, pr_body
