"""Service functions to process issues"""

import logging
from datetime import datetime

from cleankoda.core.extern.its.issue_tracking_system import IssueTrackingSystem, Issue
from cleankoda.core.types import IssueStateType

logger = logging.getLogger(__name__)


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


async def resolve_issue_for_agent(issue_id: str | None, its: IssueTrackingSystem) -> Issue | None:
    """
    Get the last issue (with issue_id) if in progress,
    or get a new issue from todo if it's not in review or in progress.

    Returns:
        Issue if issue is found and is in review or in progress.
    """

    if issue_id:
        logger.info("Looking for issue %s in issue tracking system", issue_id)
        try:
            issue = await its.get_issue_by_id(issue_id)
        except Exception:  # pylint: disable=broad-exception-caught
            issue = None

        if issue:
            # check if issue in review or in progress
            if issue.state_type == IssueStateType.IN_REVIEW:
                logger.info("Issue %s is in review. Wait for user action.", issue.id)
                return None

            if issue.state_type == IssueStateType.IN_PROGRESS:
                logger.info("Issue %s is in progress. Continue working.", issue.id)
                return issue

            logger.info("Last issue found (%s) but it is not in review or in progress.", issue.id)

    # Get a new issue from todo
    logger.info("Fetching new issue from todo.")
    issue = await its.get_next_issue_from_state(IssueStateType.TODO)
    return issue
