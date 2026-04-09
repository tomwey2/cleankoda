"""Service function for the plan."""

import logging

from app.core.localdb.agent_issues_utils import read_db_issue, update_db_issue

logger = logging.getLogger(__name__)


def save_plan_to_db(content: str) -> bool:
    """Save the implementation plan to the database.

    Args:
        content: Content of the implementation plan.

    Returns:
        True if the implementation plan was saved successfully, False otherwise.
    """
    issue = read_db_issue()
    if not issue:
        return False
    update_db_issue(issue_id=issue.issue_id, plan_content=content)
    return True


def exist_plan() -> bool:
    """Check if the implementation plan exists in the database.

    Returns:
        True if implementation plan exists, False otherwise.
    """
    issue = read_db_issue()
    if not issue:
        return False
    return bool(issue.plan_content)


def get_plan() -> str:
    """Read and return the implementation plan from database.

    Returns:
        Content of implementation plan or a default message if not found.
    """
    issue = read_db_issue()
    if not issue or not issue.plan_content:
        return "No implementation plan found in database."
    return issue.plan_content
