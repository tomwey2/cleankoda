"""Service function for the plan."""

import logging

from src.core.services.agent_states_service import get_agent_state_by_id, update_agent_state

logger = logging.getLogger(__name__)


def save_plan_to_db(content: str) -> bool:
    """Save the implementation plan to the database.

    Args:
        content: Content of the implementation plan.

    Returns:
        True if the implementation plan was saved successfully, False otherwise.
    """
    agent_state = get_agent_state_by_id()
    if not agent_state:
        return False
    update_agent_state(issue_id=agent_state.issue_id, plan_content=content)
    return True


def exist_plan() -> bool:
    """Check if the implementation plan exists in the database.

    Returns:
        True if implementation plan exists, False otherwise.
    """
    agent_state = get_agent_state_by_id()
    if not agent_state:
        return False
    return bool(agent_state.plan_content)


def get_plan() -> str:
    """Read and return the implementation plan from database.

    Returns:
        Content of implementation plan or a default message if not found.
    """
    agent_state = get_agent_state_by_id()
    if not agent_state or not agent_state.plan_content:
        return "No implementation plan found in database."
    return agent_state.plan_content
