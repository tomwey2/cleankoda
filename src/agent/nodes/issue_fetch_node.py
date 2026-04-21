"""
Issue fetch node.

Fetches issues from an issue tracking system (Trello, GitHub, Jira, etc.),
preparing them for processing by the agent.
"""

import logging

from src.core.its.its_factory import create_issue_tracking_system
from src.core.its.issue_tracking_system import IssueTrackingSystem, Issue
from src.agent.services.pull_request import (
    format_pr_review_message,
    get_latest_open_pr_for_branch,
    get_latest_pr_review_status,
)
from src.core.issue_utils import (
    fetch_review_comments,
    fetch_issue_from_state,
)
from src.agent.state import AgentState
from src.core.localdb.models import AgentSettingsDb
from src.core.types import IssueStateType

logger = logging.getLogger(__name__)


def create_issue_fetch_node(agent_settings: AgentSettingsDb):
    """Creates an issue fetch node for the agent graph."""
    its = create_issue_tracking_system(agent_settings)

    async def issue_fetch(state: AgentState) -> dict:  # pylint: disable=unused-argument
        """
        Fetches the first issue from the issue tracking system in a specified list.
        """
        if state["current_node"] != "issue_fetch":
            logger.info("--- ISSUE FETCH node ---")

        try:
            issue = await _resolve_issue(state["issue_id"], its)

            # if no issue is found, return
            if not issue:
                logger.info("There is no current issue to work on.")
                return {"issue_id": None}

            # if issue is found, determine if it is active, i.e. in todo, in progress or in review
            issue_is_active = issue.state_name in [
                its.get_state_todo(),
                its.get_state_in_progress(),
                its.get_state_in_review(),
            ]
            issue_from_todo = issue.state_name == its.get_state_todo()

            comments = []
            pr_review_message = ""
            if issue_is_active and issue.state_name == its.get_state_in_progress():
                # otherwise fetch review comments from issue tracking system and pr, in order
                # to give further information from user
                comments = await fetch_review_comments(
                    its,
                    issue.id,
                    its.get_state_in_progress(),
                    its.get_state_in_review(),
                    state["repo_branch_name"],
                )
                pr_review_message = _fetch_pr_review_info(state, issue.id)

            if issue_is_active and issue_from_todo:
                # if the issue is new and has the state "todo" then move it to "in progress"
                await its.move_issue_to_named_state(
                    issue_id=issue.id, state_name=its.get_state_in_progress()
                )

            return {
                "current_node": "issue_fetch",
                "issue_id": issue.id,
                "issue_name": issue.name,
                "issue_description": issue.description,
                "issue_state": IssueStateType.IN_PROGRESS
                if issue_is_active
                else IssueStateType.UNKNOWN,
                "issue_comments": comments,
                "issue_is_active": issue_is_active,
                "issue_from_todo": issue_from_todo,
                "issue_url": issue.url,
                "pr_review_message": pr_review_message,
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error fetching issue: %s", e)
            return {"issue_id": None}

    return issue_fetch


async def _resolve_issue(issue_id: str | None, its: IssueTrackingSystem) -> Issue | None:
    """
    Get the last issue (with issue_id) or create a new issue.
    See specification in issue-management.md.
    Returns: the issue
    """

    if issue_id:
        logger.info("Fetching issue from issue tracking system: %s", issue_id)

        try:
            issue = await its.get_issue(issue_id)
        except Exception:  # pylint: disable=broad-exception-caught
            issue = None

        if issue:
            # check if issue in review or in progress
            if issue.state_name == its.get_state_in_review():
                logger.info("Issue is in review. Wait for user action.")
                return None

            if issue.state_name == its.get_state_in_progress():
                logger.info("Issue is in progress. Add review comments.")
                return issue

            logger.info("Last issue found but it is not in review or in progress.")
            return issue

    # Get a new issue from todo
    logger.info("Fetching new issue from todo.")
    issue = await fetch_issue_from_state(its, its.get_state_todo())
    return issue


def _fetch_pr_review_info(state: AgentState, issue_id: str) -> str:
    """
    Fetch PR review info if a PR exists for the issue.

    Args:
        issue_id: The issue ID to check

    Returns:
        Tuple of (is_approved, formatted_review_message)
        - is_approved: True if PR is approved or no PR exists
        - formatted_review_message: Formatted message for SystemMessage, empty if approved
    """
    repo_branch_name = state["repo_branch_name"]
    pr = None
    if repo_branch_name:
        pr = get_latest_open_pr_for_branch(repo_branch_name)

    if not pr:
        logger.info("No PR found for issue %s", issue_id)
        return ""

    is_approved, rejection_reviews, code_comments = get_latest_pr_review_status(pr.number)

    if is_approved:
        logger.info("PR #%d for issue %s is approved", pr.number, issue_id)
        return ""

    logger.info(
        "PR #%d for issue %s has %d rejections and %d code comments",
        pr.number,
        issue_id,
        len(rejection_reviews),
        len(code_comments),
    )

    return format_pr_review_message(pr.html_url or "", rejection_reviews, code_comments)
