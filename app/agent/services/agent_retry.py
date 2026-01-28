"""
Agent retry logic helper.

Provides reusable retry logic for agent nodes that need to handle
empty responses or LLM failures.
"""

import logging

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

logger = logging.getLogger(__name__)


async def invoke_with_retry(
    llm,
    tools: list,
    messages: list[BaseMessage],
    max_attempts: int = 3,
    escalation_messages: tuple[str, str] | None = None,
) -> AIMessage:
    """
    Invoke an LLM chain with retry logic for empty responses.

    Args:
        llm: The language model to use
        tools: List of tools available to the LLM
        messages: Initial messages to send to the LLM
        max_attempts: Maximum number of retry attempts
        escalation_messages: Tuple of (ai_message, human_message) to inject on retry

    Returns:
        AIMessage response from the LLM

    Raises:
        Exception if all retries fail
    """
    current_messages = list(messages)
    current_tool_choice = "auto"

    if escalation_messages is None:
        escalation_messages = (
            "I have analyzed the situation and am ready to proceed.",
            "Good. STOP THINKING. Use a tool NOW."
        )

    for attempt in range(max_attempts):
        try:
            chain = llm.bind_tools(tools, tool_choice=current_tool_choice)
            response = await chain.ainvoke(current_messages)

            has_content = bool(response.content)
            has_tool_calls = bool(getattr(response, "tool_calls", []))

            if has_content or has_tool_calls:
                return response

            logger.warning(
                "Attempt %d/%d: Empty response. Escalating strategy...",
                attempt + 1,
                max_attempts
            )

            # Escalate by forcing tool use and adding prompting messages
            current_tool_choice = "any"
            current_messages.append(AIMessage(content=escalation_messages[0]))
            current_messages.append(HumanMessage(content=escalation_messages[1]))

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error in LLM call (Attempt %d/%d): %s", attempt + 1, max_attempts, e)
            if attempt == max_attempts - 1:
                raise

    # Should not reach here, but provide fallback
    raise RuntimeError(f"Agent stuck after {max_attempts} attempts with no valid response")


def create_fallback_message(summary: str = "Agent stuck.") -> AIMessage:
    """
    Create a fallback finish_task message for when an agent gets stuck.

    Args:
        summary: Summary message to include

    Returns:
        AIMessage with finish_task tool call
    """
    return AIMessage(
        content=summary,
        tool_calls=[
            {
                "name": "finish_task",
                "args": {"summary": summary},
                "id": "call_emergency",
                "type": "tool_call",
            }
        ],
    )
