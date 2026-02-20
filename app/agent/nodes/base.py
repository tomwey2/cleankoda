"""
Shared base helper for tool-based agent nodes.

Provides `invoke_tool_node`, which encapsulates the common LLM-invoke-with-retry
loop used by the Coder, Analyst, and Tester nodes.
"""

import logging
from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.agent.services.logging import log_agent_response
from app.agent.services.message_processing import filter_messages_for_llm, sanitize_response
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


async def invoke_tool_node(  # pylint: disable=too-many-arguments,too-many-locals,duplicate-code
    *,
    node_name: str,
    state: AgentState,
    llm: Any,
    tools: list,
    system_prompt: str,
    human_prompt: str,
    max_messages: int,
    fallback_tool_name: str,
    fallback_tool_args: dict[str, Any],
    llm_response_hook: Callable[[AgentState, AIMessage], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Shared LLM-invoke-with-retry loop for tool-based agent nodes.

    Args:
        node_name: Identifier used in logging and the returned state dict.
        state: Current agent state.
        llm: The language model to bind tools to.
        tools: Tools to bind to the LLM.
        system_prompt: Rendered system prompt string.
        human_prompt: Rendered human prompt string.
        max_messages: Maximum number of messages to pass to the LLM.
        fallback_tool_name: Tool name used in the emergency fallback AIMessage.
        fallback_tool_args: Args dict for the emergency fallback tool call.
        llm_response_hook: Optional callable invoked on a successful response.
            Receives (state, response) and returns a dict merged into the result.
    Returns:
        A state-update dict suitable for returning from a LangGraph node.
    """
    filtered_messages = filter_messages_for_llm(state["messages"], max_messages=max_messages)
    current_messages: list[BaseMessage | SystemMessage | HumanMessage] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]
    current_messages += filtered_messages

    current_tool_choice = "auto"

    for attempt in range(3):
        try:
            chain = llm.bind_tools(tools, tool_choice=current_tool_choice)
            response: AIMessage = await chain.ainvoke(current_messages)

            response = sanitize_response(response)

            tool_calls = getattr(response, "tool_calls", [])
            if tool_calls:
                log_agent_response(node_name, response, attempt=attempt + 1)

                result: dict[str, Any] = {
                    "messages": [response],
                    "current_node": node_name,
                    "current_tool_calls": tool_calls,
                    "prompt": human_prompt,
                    "system_prompt": system_prompt,
                }

                if llm_response_hook:
                    hook_result = llm_response_hook(state, response)
                    result.update(hook_result)

                return result

            logger.warning("Attempt %d: No tool calls. Escalating strategy...", attempt + 1)
            current_tool_choice = "any"
            current_messages.append(
                HumanMessage(content="ERROR: Invalid response. You MUST call a tool!")
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error in LLM call (Attempt %d): %s", attempt + 1, e)

    # Fallback
    logger.error("Agent stuck after 3 attempts. Hard exit.")

    fallback_message = AIMessage(
        content="Stuck.",
        tool_calls=[
            {
                "name": fallback_tool_name,
                "args": fallback_tool_args,
                "id": "call_emergency",
                "type": "tool_call",
            }
        ],
    )

    fallback_result: dict[str, Any] = {
        "messages": [fallback_message],
        "current_node": node_name,
    }

    if llm_response_hook:
        hook_result = llm_response_hook(state, fallback_message)
        fallback_result.update(hook_result)

    return fallback_result
