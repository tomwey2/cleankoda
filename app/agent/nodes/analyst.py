# pylint: disable=duplicate-code
"""
Defines the Analyst agent node for the agent graph.

The Analyst is a specialist agent responsible for analyzing code, answering
questions about the codebase, and providing explanations without making
any modifications.
"""

import logging
from typing import Any

from langchain.chat_models import BaseChatModel
from langchain_core.messages import AIMessage

from app.agent.nodes.base import invoke_tool_node
from app.agent.services.prompts import load_prompt
from app.agent.services.summaries import (
    append_agent_summary,
    has_finish_task_call,
    record_finish_task_summary,
)
from app.agent.state import AgentState, PlanState
from app.core.plan_utils import exist_plan, get_plan

logger = logging.getLogger(__name__)

DASHBOARD_URL = "http://localhost:5000/dashboard"


def create_analyst_node(llm: BaseChatModel, tools):
    """
    Factory function that creates the Analyst agent node.

    Args:
        llm: The language model to be used by the analyst.
        tools: A list of tools available to the analyst.

    Returns:
        A function that represents the analyst node.
    """

    async def analyst_node(state: AgentState):
        if state["current_node"] != "analyst":
            logger.info("--- ANALYST node ---")
        # Analyst may need more context for code analysis
        system_message = load_prompt("systemprompt_analyst.md", state)
        human_message = load_prompt("prompt_analyzing.md", state)

        exist_plan_before_llm_call = exist_plan()

        def _llm_response_hook(state: AgentState, response: AIMessage) -> dict[str, Any]:
            """
            Hook function to process the LLM response and update the state.

            Args:
                agent_state: The current agent state.
                response: The AIMessage response from the LLM.

            Returns:
                A dictionary containing the updated state.
            """
            result: dict[str, Any] = {"user_message": "Review the plan and approve or reject it"}

            if has_finish_task_call(message=response):
                _, agent_summary = record_finish_task_summary(
                    state, role="analyst", ai_message=response
                )

                plan_content, plan_state = _get_plan_content_and_plan_state(
                    exist_plan_before_llm_call
                )

                if plan_content:
                    agent_summary = append_agent_summary(
                        agent_summary,
                        "Dashboard",
                        f"Plan available at\n\n {DASHBOARD_URL}",
                    )

                result["agent_summary"] = agent_summary

                agent_task = state["agent_task"]
                agent_task.plan_content = plan_content
                agent_task.plan_state = plan_state
                result["agent_task"] = agent_task

            return result

        return await invoke_tool_node(
            node_name="analyst",
            state=state,
            llm=llm,
            tools=tools,
            system_prompt=system_message,
            human_prompt=human_message,
            max_messages=20,
            fallback_tool_name="finish_task",
            fallback_tool_args={"summary": "Analysis could not complete due to invalid responses."},
            llm_response_hook=_llm_response_hook,
        )

    return analyst_node


def _get_plan_content_and_plan_state(
    exist_plan_before_llm_call: bool,
) -> tuple[str | None, PlanState | None]:
    """
    Get plan info after LLM call.

    Args:
        exist_plan_before_llm_call: Whether a plan existed before the LLM call.

    Returns:
        A tuple containing the plan content and plan state.
    """
    exist_plan_after_llm_call = exist_plan()
    plan_content = get_plan() if exist_plan_after_llm_call else None
    plan_state = None
    if exist_plan_after_llm_call:
        plan_state = PlanState.CREATED
        if exist_plan_before_llm_call:
            plan_state = PlanState.UPDATED

    return plan_content, plan_state
