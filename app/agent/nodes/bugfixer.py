"""
Defines the Bugfixer agent node for the agent graph.

The Bugfixer is a specialist agent responsible for debugging code, analyzing
errors, and implementing fixes for identified issues.
"""

import logging
from typing import Any

from langchain_core.messages import BaseMessage, SystemMessage

from app.agent.services.agent_retry import create_fallback_message, invoke_with_retry
from app.agent.services.logging import log_agent_response
from app.agent.services.message_processing import filter_messages_for_llm
from app.agent.services.prompts import load_system_prompt
from app.agent.services.summaries import record_finish_task_summary
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def create_bugfixer_node(llm, tools, agent_stack):
    """
    Factory function that creates the Bugfixer agent node.

    Args:
        llm: The language model to be used by the bugfixer.
        tools: A list of tools available to the bugfixer.
        agent_stack: The technology stack (e.g., 'backend', 'frontend')
                     to load the correct system prompt.

    Returns:
        A function that represents the bugfixer node.
    """
    sys_msg = load_system_prompt(agent_stack, "bugfixer")

    async def bugfixer_node(state: AgentState):
        filtered_messages: list[BaseMessage] = filter_messages_for_llm(
            state["messages"], max_messages=15
        )
        current_messages: list[BaseMessage] = [SystemMessage(content=sys_msg)] + filtered_messages

        escalation_messages = (
            "Thinking...",
            "ERROR: Empty response. Use a tool!"
        )

        # pylint: disable=duplicate-code  # Shared retry pattern with coder by design
        try:
            response: BaseMessage = await invoke_with_retry(
                llm,
                tools,
                current_messages,
                max_attempts=3,
                escalation_messages=escalation_messages,
            )
            log_agent_response("bugfixer", response)
        except RuntimeError:
            logger.error("Agent stuck after retries. Using fallback.")
            response = create_fallback_message("Agent stuck.")
        # pylint: enable=duplicate-code

        recorded, agent_summary = record_finish_task_summary(state, "bugfixer", response)
        result: dict[str, Any] = {
            "messages": [response],
            "current_node": "bugfixer",
        }
        if recorded:
            result["agent_summary"] = agent_summary
        return result

    return bugfixer_node
