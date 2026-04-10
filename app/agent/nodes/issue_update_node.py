"""
Defines the issue update node for the agent graph.

This node is responsible for finalizing an issue on the issue tracking system. It adds a summary
comment to the issue and moves it to a "done" or "completed" list,
based on the agent's configuration.
"""

import logging
from time import sleep

from langchain_core.messages import AIMessage, ToolMessage

from app.core.issueprovider.issue_factory import create_issue_provider
from app.core.issueprovider.issue_provider import IssueProvider, Issue
from app.agent.services.summaries import get_agent_summary_entries
from app.agent.state import AgentState
from app.core.localdb.models import AgentSettingsDb

AGENT_DEFAULT_COMMENT = "Issue completed by AI Agent."

logger = logging.getLogger(__name__)


def create_issue_update_node(agent_settings: AgentSettingsDb):
    """
    Factory function that creates the issue update node.

    Args:
        agent_settings: Agent configuration containing issue provider credentials
            and settings.

    Returns:
        A function that represents the issue update node.
    """

    async def issue_update(state: AgentState) -> dict:
        """
        Updates the issue with a comment and moves it to the specified list.
        """
        if state["current_node"] != "issue_update":
            logger.info("--- ISSUE UPDATE node ---")
        issue: Issue | None = state["issue"]
        if not issue:
            logger.warning("No issue found in state")
            return {}

        logger.info("Updating issue in issue tracking system %s", issue)

        its: IssueProvider = create_issue_provider(agent_settings)

        try:
            final_comments = _build_agent_comments(state)
            for comment in final_comments:
                await its.add_comment(issue.id, comment)
                sleep(0.1)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to add comment to issue: %s", e)

        try:
            await its.move_issue_to_named_state(
                issue_id=issue.id, state_name=its.get_state_in_review()
            )

            return {
                "current_node": "issue_update",
            }
        except ValueError as exc:
            logger.warning(str(exc))
            return
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error moving issue to state: %s", e)
            return

    return issue_update


def get_agent_result(messages):
    """
    Searches backward in the history for the 'finish_task' Tool-Call.
    The summary or result of the tool call is returned.
    If not found, returns the default comment.
    """
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tool_call in msg.tool_calls:
                if tool_call["name"] == "finish_task":
                    return tool_call["args"].get("summary", AGENT_DEFAULT_COMMENT)

    return AGENT_DEFAULT_COMMENT


def _check_for_issue_creation(state: AgentState) -> tuple[bool, str | None]:
    """
    Checks if create_issue was called and returns issue info.

    Returns:
        Tuple of (was_issue_created, issue_info_message)
    """
    messages = state.get("messages", [])

    for i, msg in enumerate(messages):
        if not isinstance(msg, AIMessage) or not msg.tool_calls:
            continue

        for tool_call in msg.tool_calls:
            if tool_call["name"] != "create_issue":
                continue

            if i + 1 >= len(messages) or not isinstance(messages[i + 1], ToolMessage):
                continue

            tool_response = messages[i + 1].content
            if (
                isinstance(tool_response, str)
                and "Successfully created implementation issue" in tool_response
            ):
                return True, tool_response

    return False, None


def _build_agent_comments(state: AgentState) -> list[str]:
    """
    Builds a list of agent comments from the agent summary entries.
    If a new issue was created, adds a second comment about the issue creation.
    """
    entries = get_agent_summary_entries(state)
    if not entries:
        summary_list = [AGENT_DEFAULT_COMMENT]
    else:
        summary_list = []
        for entry in entries:
            summary_list.append(f"**Agent Update:**\n\n {entry.to_markdown()}")

    issue_created, issue_info = _check_for_issue_creation(state)

    if issue_created and issue_info:
        summary_list.append(f"**New Implementation Issue Created:**\n\n{issue_info}")

    return summary_list
