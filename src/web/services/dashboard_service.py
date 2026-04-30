"""Service layer for dashboard functionality.

This module contains business logic for the dashboard page,
separating concerns from the route handlers.
"""

import logging
import markdown

from src.core.database.models import AgentActionDb, AgentSettingsDb, AgentStatesDb
from src.core.extern.its.its_factory import create_issue_tracking_system
from src.core.services import (
    agent_actions_service,
    agent_states_service,
    agent_settings_service,
)
from src.core.types import PlanState, IssueStateType

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


async def get_template_context(user_id: str) -> dict:
    """Build complete template context for dashboard page.

    Returns:
        Dictionary with all template variables.
    """
    agent_settings: AgentSettingsDb | None = agent_settings_service.get_or_create_agent_settings(
        user_id
    )
    agent_state: AgentStatesDb | None = agent_states_service.get_agent_state_by_id(user_id)

    plan_content = ""
    plan_exists = False
    issue_description_html = ""
    agent_actions: list[AgentActionDb] = []
    agent_image = ""

    agent_age = "junior"
    agent_gender = "male"
    if agent_settings:
        if agent_settings.agent_skill_level:
            agent_age = agent_settings.agent_skill_level.lower()
        if agent_settings.agent_gender:
            agent_gender = agent_settings.agent_gender.lower()
    agent_activity = "is-waiting"

    if agent_state:
        agent_actions = agent_actions_service.get_agent_actions_by_issue_id(
            user_id, agent_state.issue_id
        )
        # logger.info("current node: %s", agent_state.current_node)
        plan_content = (
            markdown.markdown(agent_state.plan_content) if agent_state.plan_content else ""
        )
        plan_exists = bool(agent_state.plan_content)
        issue_description_html = (
            markdown.markdown(agent_state.issue_description)
            if agent_state.issue_description
            else ""
        )

        if agent_state.issue_state == IssueStateType.IN_PROGRESS.value:
            agent_activity = "is-working"
        elif agent_state.issue_state == IssueStateType.IN_REVIEW.value:
            agent_activity = "is-happy"

    agent_image = f"{agent_age}-{agent_gender}-{agent_activity}.png"

    return {
        "issue_id": agent_state.issue_id if agent_state else None,
        "issue_name": agent_state.issue_name if agent_state else None,
        "issue_description": agent_state.issue_description if agent_state else None,
        "issue_type": agent_state.issue_type if agent_state else None,
        "issue_skill_level": agent_state.issue_skill_level if agent_state else None,
        "plan_content": plan_content,
        "plan_exists": plan_exists,
        "plan_state": agent_state.plan_state if agent_state else None,
        "issue_description_html": issue_description_html,
        "current_node": "todo",
        "agent_actions": agent_actions,
        "working_state": agent_state.working_state if agent_state else None,
        "user_message": agent_state.user_message if agent_state else None,
        "repo_pr_url": agent_state.repo_pr_url if agent_state else None,
        "agent_skill_level": agent_settings.agent_skill_level if agent_settings else None,
        "agent_image": agent_image,
    }


def _get_its(user_id: str):
    """Creates and returns a issue provider from the current agent settings."""
    agent_settings: AgentSettingsDb = agent_settings_service.get_or_create_agent_settings(user_id)
    return create_issue_tracking_system(agent_settings)


async def add_plan_rejection_comment(user_id: str, issue_id: str, rejection_reason: str) -> None:
    """Adds a comment to the issue with the rejection reason.

    Raises:
        Exception: If adding the comment fails.
    """
    logger.info("Adding rejection comment to issue %s", issue_id)
    its = _get_its(user_id)
    await its.add_comment_to_issue(issue_id, rejection_reason)


async def move_issue_to_in_progress(user_id: str, issue_id: str) -> bool:
    """Moves the issue to the state in progress."""
    logger.info("Moving issue %s to in progress", issue_id)
    its = _get_its(user_id)
    await its.move_issue_to_named_state(issue_id, state_name=its.get_state_in_progress())
    return True


def _validate_plan_review_input(new_state: PlanState, rejection_reason: str | None):
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
    if not new_state or not isinstance(new_state, PlanState):
        raise PlanReviewError("Plan state is required and must be a PlanState.")

    if new_state not in [PlanState.APPROVED, PlanState.REJECTED]:
        raise PlanReviewError("Invalid state. Must be 'APPROVED' or 'REJECTED'.")

    rejection_reason = (rejection_reason or "").strip()

    if new_state == PlanState.REJECTED and not rejection_reason:
        raise PlanReviewError("A rejection reason is required.")


def _rollback_issue_state(user_id: str, issue_id: str, original_state: PlanState) -> bool:
    """Attempt to rollback issue state to original value.

    Args:
        issue_id: The issue ID to rollback.
        original_state: The original plan state to restore.

    Returns:
        True if rollback succeeded, False otherwise.
    """
    try:
        rollback_issue = agent_states_service.update_agent_state(
            user_id=user_id, issue_id=issue_id, plan_state=original_state
        )
        if not rollback_issue:
            logger.error("Failed to rollback issue state for issue %s", issue_id)
            return False
        return True
    except (ValueError, RuntimeError, KeyError) as exc:
        logger.exception("Exception during rollback for issue %s: %s", issue_id, exc)
        return False


async def process_plan_review(
    user_id: str, new_state: PlanState, rejection_reason: str | None
) -> dict:
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
    _validate_plan_review_input(new_state, rejection_reason)
    rejection_reason = (rejection_reason or "").strip()

    agent_state = agent_states_service.get_agent_state_by_id(user_id)
    if not agent_state:
        raise PlanReviewError("No active issue found in database.", status_code=HTTP_NOT_FOUND)

    # Store original state for potential rollback
    original_plan_state = PlanState.from_string(agent_state.plan_state)

    if new_state == PlanState.REJECTED and original_plan_state not in (
        PlanState.CREATED,
        PlanState.UPDATED,
    ):
        raise PlanReviewError(
            "Plan can only be rejected when it is in review.", status_code=HTTP_CONFLICT
        )

    try:
        # Update issue state first
        updated_agent_state = agent_states_service.update_agent_state(
            user_id=user_id, issue_id=agent_state.issue_id, plan_state=new_state.value
        )
        if not updated_agent_state:
            raise PlanReviewError("Failed to update issue", status_code=HTTP_INTERNAL_SERVER_ERROR)

        # Add rejection comment if needed
        if new_state == PlanState.REJECTED and rejection_reason:
            try:
                await add_plan_rejection_comment(
                    user_id, updated_agent_state.issue_id, rejection_reason
                )
            except Exception as exc:
                logger.exception(
                    "Failed to add rejection comment to issue %s. Rolling back state change.",
                    updated_agent_state.issue_id,
                )
                # Rollback the state change
                _rollback_issue_state(user_id, agent_state.issue_id, original_plan_state)
                raise PlanReviewError(
                    "Failed to add rejection comment. Plan state has been rolled back.",
                    status_code=HTTP_INTERNAL_SERVER_ERROR,
                ) from exc

        # Move issue to in progress
        try:
            moved = await move_issue_to_in_progress(user_id, updated_agent_state.issue_id)
        except Exception as exc:
            logger.exception(
                "Failed to move issue %s to in progress. Rolling back state change.",
                updated_agent_state.issue_id,
            )
            # Rollback the state change
            _rollback_issue_state(user_id, agent_state.issue_id, original_plan_state)
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
            "issue_id": updated_agent_state.issue_id,
            "plan_state": updated_agent_state.plan_state,
        }

    except PlanReviewError:
        # Re-raise our custom errors
        raise
    except Exception as exc:
        logger.exception("Unexpected error in process_plan_review")
        # Attempt rollback if we have an original state
        if "original_plan_state" in locals():
            _rollback_issue_state(user_id, agent_state.issue_id, original_plan_state)
        raise PlanReviewError(
            "An unexpected error occurred. Plan state has been rolled back.",
            status_code=HTTP_INTERNAL_SERVER_ERROR,
        ) from exc
