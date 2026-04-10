"""Service layer for dashboard functionality.

This module contains business logic for the dashboard page,
separating concerns from the route handlers.
"""

import logging
import markdown

from app.core.localdb.agent_actions_utils import read_db_agent_actions
from app.core.localdb.agent_issues_utils import read_db_issue, update_db_issue
from app.core.localdb.models import AgentActionDb, AgentSettingsDb, AgentStatesDb
from app.core.its.issue_factory import create_issue_provider
from app.web.services import settings_service

logger = logging.getLogger(__name__)

# HTTP status codes
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_INTERNAL_SERVER_ERROR = 500


class PlanReviewError(Exception):
    """Raised when plan review processing fails."""

    def __init__(self, message: str, status_code: int = HTTP_BAD_REQUEST):
        super().__init__(message)
        self.status_code = status_code


async def get_template_context() -> dict:
    """Build complete template context for dashboard page.

    Returns:
        Dictionary with all template variables.
    """
    agent_issue: AgentStatesDb | None = read_db_issue()

    plan_content = ""
    plan_exists = False
    issue_description_html = ""
    agent_actions: list[AgentActionDb] = []

    if agent_issue:
        agent_actions = read_db_agent_actions(agent_issue)
        # logger.info("current node: %s", agent_issue.current_node)
        plan_content = (
            markdown.markdown(agent_issue.plan_content) if agent_issue.plan_content else ""
        )
        plan_exists = bool(agent_issue.plan_content)
        issue_description_html = (
            markdown.markdown(agent_issue.issue_description)
            if agent_issue.issue_description
            else ""
        )

    return {
        "agent_issue": agent_issue,
        "plan_content": plan_content,
        "plan_exists": plan_exists,
        "issue_description_html": issue_description_html,
        "current_node": "todo",
        "agent_actions": agent_actions,
    }


def _get_its():
    """Creates and returns a issue provider from the current agent settings."""
    agent_settings: AgentSettingsDb = settings_service.get_or_create_settings()
    return create_issue_provider(agent_settings)


async def add_plan_rejection_comment(issue_id: str, rejection_reason: str) -> None:
    """Adds a comment to the issue with the rejection reason.

    Raises:
        Exception: If adding the comment fails.
    """
    logger.info("Adding rejection comment to issue %s", issue_id)
    its = _get_its()
    await its.add_comment(issue_id, rejection_reason)


async def move_issue_to_in_progress(issue_id: str) -> bool:
    """Moves the issue to the state in progress."""
    logger.info("Moving issue %s to in progress", issue_id)
    its = _get_its()
    await its.move_issue_to_named_state(issue_id, state_name=its.get_state_in_progress())
    return True


def _validate_plan_review_input(new_state: str | None, rejection_reason: str | None) -> str:
    """Validate and normalize plan review input.

    Args:
        new_state: The new plan state ('approved' or 'rejected').
        rejection_reason: Reason for rejection (required if new_state is 'rejected').

    Returns:
        Normalized new_state string.

    Raises:
        PlanReviewError: If validation fails.
    """
    # Input validation
    if not new_state or not isinstance(new_state, str):
        raise PlanReviewError("Plan state is required and must be a string.")

    new_state = new_state.strip().lower()
    if new_state not in ["approved", "rejected"]:
        raise PlanReviewError("Invalid state. Must be 'approved' or 'rejected'.")

    rejection_reason = (rejection_reason or "").strip()

    if new_state == "rejected" and not rejection_reason:
        raise PlanReviewError("A rejection reason is required.")

    return new_state


def _rollback_issue_state(issue_id: str, original_state: str) -> bool:
    """Attempt to rollback issue state to original value.

    Args:
        issue_id: The issue ID to rollback.
        original_state: The original plan state to restore.

    Returns:
        True if rollback succeeded, False otherwise.
    """
    try:
        rollback_issue = update_db_issue(issue_id, plan_state=original_state)
        if not rollback_issue:
            logger.error("Failed to rollback issue state for issue %s", issue_id)
            return False
        return True
    except (ValueError, RuntimeError, KeyError) as exc:
        logger.exception("Exception during rollback for issue %s: %s", issue_id, exc)
        return False


async def process_plan_review(new_state: str | None, rejection_reason: str | None) -> dict:
    """Handle plan review transitions and side-effects.

    Args:
        new_state: The new plan state ('approved' or 'rejected').
        rejection_reason: Reason for rejection (required if new_state is 'rejected').

    Returns:
        Dictionary with success message and issue details.

    Raises:
        PlanReviewError: If validation fails or operations cannot be completed.
    """
    # Validate input
    new_state = _validate_plan_review_input(new_state, rejection_reason)
    rejection_reason = (rejection_reason or "").strip()

    issue = read_db_issue()
    if not issue:
        raise PlanReviewError("No active issue found in database.", status_code=HTTP_NOT_FOUND)

    if new_state == "rejected" and issue.plan_state not in ("created", "updated"):
        raise PlanReviewError(
            "Plan can only be rejected when it is in review.", status_code=HTTP_CONFLICT
        )

    # Store original state for potential rollback
    original_plan_state = issue.plan_state

    try:
        # Update issue state first
        updated_issue = update_db_issue(issue.issue_id, plan_state=new_state)
        if not updated_issue:
            raise PlanReviewError("Failed to update issue", status_code=HTTP_INTERNAL_SERVER_ERROR)

        # Add rejection comment if needed
        if new_state == "rejected" and rejection_reason:
            try:
                await add_plan_rejection_comment(updated_issue.issue_id, rejection_reason)
            except Exception as exc:
                logger.exception(
                    "Failed to add rejection comment to issue %s. Rolling back state change.",
                    updated_issue.issue_id,
                )
                # Rollback the state change
                _rollback_issue_state(issue.issue_id, original_plan_state)
                raise PlanReviewError(
                    "Failed to add rejection comment. Plan state has been rolled back.",
                    status_code=HTTP_INTERNAL_SERVER_ERROR,
                ) from exc

        # Move issue to in progress
        try:
            moved = await move_issue_to_in_progress(updated_issue.issue_id)
        except Exception as exc:
            logger.exception(
                "Failed to move issue %s to in progress. Rolling back state change.",
                updated_issue.issue_id,
            )
            # Rollback the state change
            _rollback_issue_state(issue.issue_id, original_plan_state)
            raise PlanReviewError(
                "Failed to move issue to in progress. Plan state has been rolled back.",
                status_code=HTTP_INTERNAL_SERVER_ERROR,
            ) from exc

        if not moved:
            raise PlanReviewError(
                "Failed to move issue to in progress", status_code=HTTP_INTERNAL_SERVER_ERROR
            )

        return {
            "message": f"Plan state updated to {new_state}",
            "issue_id": updated_issue.issue_id,
            "plan_state": updated_issue.plan_state,
        }

    except PlanReviewError:
        # Re-raise our custom errors
        raise
    except Exception as exc:
        logger.exception("Unexpected error in process_plan_review")
        # Attempt rollback if we have an original state
        if "original_plan_state" in locals():
            _rollback_issue_state(issue.issue_id, original_plan_state)
        raise PlanReviewError(
            "An unexpected error occurred. Plan state has been rolled back.",
            status_code=HTTP_INTERNAL_SERVER_ERROR,
        ) from exc
