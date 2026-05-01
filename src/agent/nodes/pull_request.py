"""Create a pull request node"""

import logging
from typing import Any, Dict

from src.agent.services.git_workspace import (
    git_commit,
    git_has_changes,
    git_push,
    git_stage_all,
)
from src.agent.services.summaries import append_agent_summary, build_agent_summary_markdown
from src.agent.state import AgentState, AgentSummary
from src.agent.utils import get_workspace
from src.core.types import IssueType
from src.core.database.models import AgentSettingsDb, UserCredentialDb
from src.core.services.credentials_service import get_credential_by_id
from src.agent.runtime import RuntimeSettings
from src.core.extern.vcs.version_control_system import VersionControlSystem

logger = logging.getLogger(__name__)


ROLE_PREFIX_MAP = {
    IssueType.CODING: "feat",
    IssueType.BUGFIXING: "fix",
    IssueType.ANALYZING: "chore",
    IssueType.UNKNOWN: "chore",
}


def create_pull_request_node(runtime: RuntimeSettings):
    """Create a pull request node"""
    agent_settings: AgentSettingsDb = runtime.agent_settings
    vcs: VersionControlSystem = runtime.vcs
    repo_credential: UserCredentialDb | None = get_credential_by_id(
        agent_settings.vcs_credential_id
    )
    if not repo_credential:
        raise ValueError("No repo credential found")

    async def pull_request_node(state: AgentState) -> Dict[str, Any]:
        if state["current_node"] != "pull_request":
            logger.info("--- PULL REQUEST node ---")

        repo_pr_url = state.get("repo_pr_url")
        repo_pr_number = state.get("repo_pr_number")
        success, summary_entries = _commit_and_push(repo_credential, state)
        if success:
            pr_title = state.get("issue_name") or "Automated Fix"
            pr_body = _build_pr_body(state)
            pr_branch = state.get("repo_branch_name")
            if repo_pr_url:
                await vcs.add_comment_to_pr(repo_pr_number, pr_body)
            else:
                pr = await vcs.create_pull_request(pr_title, pr_body, pr_branch)
                if pr:
                    repo_pr_url = pr.html_url
                    repo_pr_number = pr.number

        user_message = (
            "Review the pull request. If you approve it, move the task to 'done'.\n"
            + "If you reject it, comment the task and move it to 'in progress'."
        )

        if not success:
            user_message = (
                "Pull request creation/update failed. Please review the logs and try again."
            )

        return {
            "current_node": "pull_request",
            "agent_summary": summary_entries,
            "repo_pr_url": repo_pr_url,
            "repo_pr_number": repo_pr_number,
            "user_message": user_message,
        }

    return pull_request_node


def _append_summary(
    summary_entries: list[AgentSummary], state: AgentState, title: str, message: str
) -> list[AgentSummary]:
    summary_entries = append_agent_summary(summary_entries, title, message)
    state["agent_summary"] = summary_entries
    return summary_entries


def _commit_and_push(repo_credential: UserCredentialDb, state: AgentState):
    summary_entries = list(state.get("agent_summary") or [])

    has_changes = git_has_changes(get_workspace())
    logger.info("Git status check: %s changes found", "Some" if has_changes else "No")

    failure_detected = False
    failure_reason = "Pull request skipped"

    commit_message = _generate_commit_message(state)
    if not has_changes:
        logger.info("No changes detected, skipping Git workflow")
        failure_detected = True
        failure_reason = "Pull request skipped: no changes detected"
    elif not git_stage_all(work_dir=get_workspace()):
        logger.error("Git add failed, skipping remaining Git operations")
        failure_detected = True
        failure_reason = "Pull request failed: git add failed"
    elif not git_commit(work_dir=get_workspace(), message=commit_message):
        logger.error("Git commit failed, skipping remaining Git operations")
        failure_detected = True
        failure_reason = "Pull request failed: git commit failed"

    if failure_detected:
        summary_entries = _append_summary(summary_entries, state, "PR", failure_reason)
        return False, summary_entries

    push_success, push_msg = git_push(
        work_dir=get_workspace(), repo_token=repo_credential.api_token
    )
    if not push_success:
        logger.error("Git push failed: %s", push_msg)
        failure_reason = f"Pull request failed: git push failed ({push_msg})"
        summary_entries = _append_summary(summary_entries, state, "PR", failure_reason)
        return False, summary_entries

    return True, summary_entries


def _generate_commit_message(state: AgentState) -> str:
    """Generate a concise commit message from the latest agent summary."""
    summaries = state.get("agent_summary") or []

    summary_text = ""
    summary_role: str | None = None

    for entry in summaries:
        if entry.role.lower() == "tester":
            continue
        summary_text = entry.summary
        summary_role = entry.role
        break

    if not summary_text:
        return "fix: automated test-driven changes"

    issue_type = state.get("issue_type")
    prefix = ROLE_PREFIX_MAP.get(issue_type, "chore")

    first_line = f"{prefix}: {summary_text}"
    if len(first_line) > 75:
        first_line = first_line[:72].rstrip() + "..."

    if issue_type in {IssueType.CODING, IssueType.BUGFIXING} and summary_role:
        role_entries = [
            entry.summary for entry in summaries if entry.role.lower() == summary_role.lower()
        ]
        details = _build_role_details(role_entries)
        if details:
            return f"{first_line}\n\n{details}"

    return first_line


def _build_role_details(role_entries: list[str]) -> str | None:
    """Return formatted detail bullet list for role entries."""
    if len(role_entries) <= 1:
        return None

    filtered_entries: list[str] = []
    previous_text: str | None = None
    for current_text in role_entries:
        if current_text and current_text != previous_text:
            filtered_entries.append(current_text)
        previous_text = current_text

    if not filtered_entries:
        return None

    return "\n".join(f"- {text}" for text in filtered_entries)


def _build_pr_body(state: AgentState) -> str:
    """
    Build the PR title and body using the issue name and agent summaries.
    """
    aggregated_summary = build_agent_summary_markdown(
        state,
        heading="## Agent Update",
        bullet_prefix="- ",
        line_separator="\n",
    )
    pr_body_summary = aggregated_summary

    pr_description = (state.get("pr_description") or "").strip()
    if pr_description:
        pr_body = pr_description
        if pr_body_summary:
            pr_body += f"\n\n{pr_body_summary}"
    else:
        pr_body = "Automated changes after successful tests."
        if pr_body_summary:
            pr_body += f"\n\n{pr_body_summary}"

    return pr_body
