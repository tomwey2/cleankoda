"""Tool for adding comments to issues."""

import logging

from langchain.tools import ToolRuntime, tool

from src.core.database.models import AgentSettingsDb
from src.core.its.its_factory import create_issue_tracking_system

logger = logging.getLogger(__name__)


@tool
async def add_issue_comment(
    comment: str,
    runtime: ToolRuntime[AgentSettingsDb, dict],
) -> str:
    """
    Adds a comment to the current issue in the issue tracking system.

    Args:
        comment: The comment text to add to the issue.
        runtime: The runtime context containing the current AgentSettings.
    Returns:
        Confirmation message with the comment details.
    """
    try:
        # Extract the current issue from AgentState
        current_issue = runtime.state.get("issue")
        if not current_issue:
            return "Error: No current issue found in state"

        issue_id = current_issue.id
        issue_name = current_issue.name

        # Create issue provider and add comment
        agent_settings = runtime.context
        if not agent_settings:
            return "Error: No agent settings found in runtime context"

        issue_provider = create_issue_tracking_system(agent_settings)
        await issue_provider.add_comment_to_issue(issue_id, comment)

        logger.info(
            "Added comment to issue '%s' (%s): %s",
            issue_name,
            issue_id,
            comment[:100] + "..." if len(comment) > 100 else comment,
        )

        return (
            f"Successfully added comment to issue '{issue_name}' (ID: {issue_id})"
            + f"\nComment: {comment}"
        )

    except ValueError as e:
        logger.error("Failed to add comment: %s", str(e))
        return f"Error: {str(e)}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Issue provider error: %s", str(e))
        return f"Failed to add comment: {str(e)}"
