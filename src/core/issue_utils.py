"""Service functions to process issues"""

import logging
from datetime import datetime


from src.core.its.issue_tracking_system import (
    IssueTrackingSystem,
    Issue,
)

logger = logging.getLogger(__name__)


async def fetch_issue_from_state(its: IssueTrackingSystem, state_name: str) -> Issue | None:
    """Fetch an issue from with a state."""
    issue_states = await its.get_states()
    target_state = next(
        (data for data in issue_states if data["name"] == state_name),
        None,
    )

    if not target_state:
        logger.warning("%s state not found", state_name)
        return None

    state_id = target_state["id"]
    logger.info("Found %s state id: %s", state_name, state_id)

    issues = await its.get_next_issue_from_state(state_id)
    if not issues:
        logger.info("No open issues found in %s.", state_name)
        return None

    return issues[0]


async def fetch_comments_since(
    its: IssueTrackingSystem,
    issue_id: str,
    since_timestamp: datetime | None,
) -> list:
    """
    Fetch comments between the since_timestamp and now.

    Args:
        its: IssueTrackingSystem
        issue_id: id of issue
        since_timestamp: datetime to fetch comments since

    Returns:
        List of comments between the since_timestamp and now.
    """
    all_comments = await its.get_comments_from_issue(issue_id)

    comments = (
        filter_comments_between_timestamps(
            all_comments,
            since_timestamp,
            datetime.now(),
        )
        if since_timestamp
        else all_comments
    )

    if comments:
        logger.info("Found comments to append")
        for comment in comments:
            logger.info("comment: %s", comment.text)
    else:
        logger.info("No comments to append")

    return comments


def filter_comments_between_timestamps(comments: list, start: datetime, end: datetime) -> list:
    """Filters comments between two timestamps (inclusive)."""
    filtered_comments = []
    for comment in comments:
        if start <= comment.date <= end:
            filtered_comments.append(comment)
    return filtered_comments
