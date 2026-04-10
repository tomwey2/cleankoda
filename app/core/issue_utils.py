"""Service functions to process issues"""

import logging
from datetime import datetime
from typing import Optional


from app.core.its.issue_tracking_system import (  # pylint: disable=unused-import
    IssueTrackingSystem,
    Issue,
)
from app.agent.services.pull_request import check_pr_exists_for_branch
from app.core.localdb.agent_issues_utils import read_db_issue

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

    issues = await its.get_issues_from_state(state_id)
    if not issues:
        logger.info("No open issues found in %s.", state_name)
        return None

    return issues[0]


async def move_issue_to_state(
    its: IssueTrackingSystem,
    issue: Issue,
    issue_state_name: str,
) -> Issue:
    """
    Moves the issue to the in-progress state before issue processing begins.
    """
    modified_issue: Optional[Issue] = issue
    if not issue_state_name:
        logger.warning("issue_in_progress_state not configured, skipping move to in-progress state")
    else:
        logger.info(
            "Moving issue %s to in-progress state: %s",
            issue.id,
            issue_state_name,
        )

        try:
            await its.move_issue_to_named_state(issue.id, issue_state_name)
            modified_issue = await its.get_issue(issue.id)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to move issue to in-progress state: %s", e)

    match modified_issue:
        case Issue():
            return modified_issue
        case None:
            raise RuntimeError("modified_issue is none")


async def fetch_review_comments(
    its: IssueTrackingSystem,
    issue_id: str,
    in_progress_state_name: str,
    in_review_state_name: str,
) -> list:
    """
    Fetch comments from review if issue was returned from review to in-progress.

    Args:
        issue_provider: IssueProvider
        issue_id: id of issue
        original_state_name: name of state before issue was moved to in-progress
        issue_in_progress_state_name: name of in-progress state
        review_state_name: name of review state

    Returns:
        List of comments if issue was in review and returned, empty list otherwise.
    """
    comments = []
    # if issue was in review and returned to in-progress,
    # fetch comments between review and move to in-progress
    all_comments = await its.get_comments(issue_id)

    if its.get_type() == "github":
        # For GitHub, only return last comment if a PR exists for the branch
        db_issue = read_db_issue(issue_id=issue_id)
        repo_branch_name = db_issue.repo_branch_name
        if repo_branch_name and check_pr_exists_for_branch(repo_branch_name):
            return all_comments[-1:] if all_comments else []
        return []

    latest_move = await get_latest_move_to_in_progress(
        its, issue_id, in_review_state_name, in_progress_state_name
    )
    logger.info("Latest move: %s", latest_move)
    if latest_move:
        comments = filter_comments_between_timestamps(
            all_comments,
            latest_move["review_timestamp"],
            latest_move["return_timestamp"],
        )
        logger.info("Found move from review to in-progress")
    else:
        logger.info("No move from review to in-progress found")

    if comments:
        logger.info("Found comments to append")
        for comment in comments:
            logger.info("comment: %s", comment.text)
    else:
        logger.info("No comments to append")

    return comments


async def get_latest_move_to_in_progress(
    its: IssueTrackingSystem,
    issue_id: str,
    review_state_name: str,
    in_progress_state_name: str,
) -> dict | None:
    """Returns timestamps if the latest move was from review to in-progress.

    Returns:
        dict with 'review_timestamp' and 'return_timestamp' if the latest move
        was from review to in-progress, None otherwise.
    """
    try:
        state_moves = await its.get_state_moves(issue_id)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.warning(
            "Failed to fetch state moves for issue %s: %s.",
            issue_id,
            e,
        )
        return None

    if not state_moves:
        return None

    # Process moves chronologically to determine review/in-progress transitions
    sorted_moves = sorted(state_moves, key=lambda move: move.date)

    # Find moves from review_state to in_progress_state
    # Each move has state_before and state_after
    review_to_progress_moves = []
    for idx, move in enumerate(sorted_moves):
        if move.state_before == review_state_name and move.state_after == in_progress_state_name:
            # Find when the issue entered the review state
            # Look backwards for the previous move that resulted in the review state
            review_timestamp = None
            for prev_move in reversed(sorted_moves[:idx]):
                if prev_move.state_after == review_state_name:
                    review_timestamp = prev_move.date
                    break

            # If we can't find when it entered review, skip this move
            if review_timestamp:
                review_to_progress_moves.append(
                    {
                        "review_timestamp": review_timestamp,  # When it entered review
                        "return_timestamp": move.date,  # When it moved back to in-progress
                    }
                )

    if not review_to_progress_moves:
        logger.info(
            "Issue %s has no moves from '%s' to '%s'.",
            issue_id,
            review_state_name,
            in_progress_state_name,
        )
        return None

    # Get the latest such move (most recent return to in-progress from review)
    latest_move = max(review_to_progress_moves, key=lambda x: x["return_timestamp"])
    logger.info(
        "Issue %s last moved from '%s' to '%s' at %s (review was at %s).",
        issue_id,
        review_state_name,
        in_progress_state_name,
        latest_move["return_timestamp"].isoformat(),
        latest_move["review_timestamp"].isoformat(),
    )
    return latest_move


def filter_comments_between_timestamps(comments: list, start: datetime, end: datetime) -> list:
    """Filters comments between two timestamps (inclusive)."""
    filtered_comments = []
    for comment in comments:
        if start <= comment.date <= end:
            filtered_comments.append(comment)
    return filtered_comments
