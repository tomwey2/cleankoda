"""
Issue fetch node.

Fetches issues from an issue tracking system (Trello, GitHub, Jira, etc.),
preparing them for processing by the agent.
"""

import logging

from app.core.issueprovider.issue_factory import create_issue_provider
from app.core.issueprovider.issue_provider import IssueProvider, Issue
from app.agent.services.pull_request import (
    format_pr_review_message,
    get_latest_open_pr_for_branch,
    get_latest_pr_review_status,
)
from app.core.issue_utils import (
    fetch_review_comments,
    fetch_issue_from_state,
    move_issue_to_state,
)
from app.agent.state import AgentState
from app.core.localdb.models import AgentSettingsDb, AgentStatesDb
from app.core.localdb.agent_issues_utils import (
    create_db_issue,
    read_db_issue,
    delete_db_issue,
)

logger = logging.getLogger(__name__)


def create_issue_fetch_node(agent_settings: AgentSettingsDb):
    """Creates an issue fetch node for the agent graph."""
    its = create_issue_provider(agent_settings)

    async def issue_fetch(state: AgentState) -> dict:  # pylint: disable=unused-argument
        """
        Fetches the first issue from the issue tracking system in a specified list.
        """
        if state["current_node"] != "issue_fetch":
            logger.info("--- ISSUE FETCH node ---")

        try:
            issue, agent_issue, issue_is_new = await _resolve_issue(state["agent_issue"], its)

            if not issue:
                logger.info("There is no current issue to work on.")
                return {"issue": None}

            comments = []
            pr_review_message = ""
            if issue_is_new:
                # if the issue is new and has the state "todo" then clean up the workspace
                issue = await _cleanup_new_issue(issue, its)
                issue = await _cleanup_new_issue(issue, its)
            else:
                # otherwise fetch review comments from issue tracking system and pr, in order
                # to give further information from user
                comments = await fetch_review_comments(
                    its,
                    issue.id,
                    its.get_state_in_progress(),
                    its.get_state_in_review(),
                )
                pr_review_message = _fetch_pr_review_info(issue.id)

            return {
                "issue": issue,
                "issue_comments": comments,
                "pr_review_message": pr_review_message,
                "agent_issue": agent_issue,
                "current_node": "issue_fetch",
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error fetching issue: %s", e)
            return {"issue": None}

    return issue_fetch


async def _cleanup_new_issue(issue: Issue, its: IssueProvider) -> Issue:
    """
    Process the issue and prepare the return value.
    """
    logger.info("Processing issue ID: %s - %s", issue.id, issue.name)
    issue = await move_issue_to_state(
        its=its,
        issue=issue,
        issue_state_name=its.get_state_in_progress(),
    )
    return issue


async def _resolve_issue(
    agent_issue: AgentStatesDb | None, its: IssueProvider
) -> tuple[Issue | None, AgentStatesDb | None, bool]:
    """
    Get the last issue (with issue_id) or create a new issue.
    See specification in issue-management.md.
    Returns:
        the issue
        true if the issue is new (from todo) otherwise false.
    """

    if agent_issue:
        logger.info("Fetching issue from issue tracking system: %s", agent_issue.issue_id)

        try:
            issue = await its.get_issue(agent_issue.issue_id)
        except Exception:  # pylint: disable=broad-exception-caught
            issue = None

        if issue:
            # check if issue in review or in progress
            if issue.state_name == its.get_state_in_review():
                logger.info("Issue is in review. Wait for user action.")
                return None, agent_issue, False

            if issue.state_name == its.get_state_in_progress():
                logger.info("Issue is in progress. Add review comments.")
                return issue, agent_issue, False

            logger.info("Last issue found but it is not in review or in progress.")

    # Get a new issue from todo
    logger.info("Fetching new issue from todo.")
    issue = await fetch_issue_from_state(its, its.get_state_todo())
    # update local db: remove the old issue and insert the new issue
    if issue:
        if agent_issue:
            delete_db_issue(agent_issue.issue_id)
        agent_issue = create_db_issue(issue.id, issue.name)
    return issue, agent_issue, True


def _fetch_pr_review_info(issue_id: str) -> str:
    """
    Fetch PR review info if a PR exists for the issue.

    Args:
        issue_id: The issue ID to check

    Returns:
        Tuple of (is_approved, formatted_review_message)
        - is_approved: True if PR is approved or no PR exists
        - formatted_review_message: Formatted message for SystemMessage, empty if approved
    """
    db_issue = read_db_issue(issue_id=issue_id)
    repo_pr_number = db_issue.repo_pr_number
    repo_pr_url = db_issue.repo_pr_url

    if not repo_pr_number:
        repo_branch_name = db_issue.repo_branch_name
        if repo_branch_name:
            pr = get_latest_open_pr_for_branch(repo_branch_name)
            if pr:
                repo_pr_number = pr.number
                repo_pr_url = pr.html_url

    if not repo_pr_number:
        logger.info("No PR found for issue %s", issue_id)
        return ""

    is_approved, rejection_reviews, code_comments = get_latest_pr_review_status(repo_pr_number)

    if is_approved:
        logger.info("PR #%d for issue %s is approved", repo_pr_number, issue_id)
        return ""

    logger.info(
        "PR #%d for issue %s has %d rejections and %d code comments",
        repo_pr_number,
        issue_id,
        len(rejection_reviews),
        len(code_comments),
    )

    return format_pr_review_message(repo_pr_url or "", rejection_reviews, code_comments)
