"""
Defines the router node for the agent graph.

This node is responsible for the initial analysis of an issue. It uses a
specialized LLM call to classify the user's request and decide which
specialist agent (e.g., Coder, Analyst) should handle it next.
"""

import logging
from typing import Dict, Literal

from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from pydantic import BaseModel, Field

from app.agent.services.message_processing import filter_messages_for_llm
from app.agent.state import AgentState
from app.agent.services.prompts import load_prompt
from app.core.types import SkillLevelType, PlanState, IssueType

logger = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods
class RouterDecision(BaseModel):
    """Classify the incoming issue into the correct category and skill level."""

    issue_type: Literal[IssueType.CODING, IssueType.BUGFIXING, IssueType.ANALYZING] = Field(
        description="The specific type of the issue."
    )
    issue_skill_level: Literal[SkillLevelType.JUNIOR, SkillLevelType.SENIOR] = Field(
        description="Must be 'junior' or 'senior'"
    )
    reasoning: str = Field(description="Why this classification was chosen")


def create_router_node(llm):
    """
    Factory function that creates the router node for the agent graph.

    Args:
        llm: The language model to be used for routing decisions.

    Returns:
        A function that represents the router node.
    """
    structured_llm = llm.with_structured_output(RouterDecision, method="json_mode")

    async def router_node(state: AgentState) -> Dict[str, str]:
        if state["current_node"] != "router":
            logger.info("--- ROUTER node ---")
        system_message = load_prompt("systemprompt_router.md", state)
        human_message = load_prompt("prompt_routing.md", state)
        # Router only needs the original issue to make routing decision
        filtered_messages = filter_messages_for_llm(state["messages"], max_messages=3)
        current_messages: list[BaseMessage | SystemMessage | HumanMessage] = [
            SystemMessage(content=system_message),
            HumanMessage(content=human_message),
        ]
        current_messages += filtered_messages

        response = await structured_llm.ainvoke(current_messages)
        logger.info("Issue type: %s", response.issue_type)
        logger.info("Issue skill level: %s", response.issue_skill_level)
        logger.info("Issue reasoning: %s", response.reasoning)

        issue_type = IssueType.from_string(response.issue_type)

        next_step = "reject"
        if issue_type == IssueType.ANALYZING:
            next_step = "analyst"
        elif issue_type == IssueType.BUGFIXING:
            next_step = "coder"
        elif issue_type == IssueType.CODING:
            next_step = route_to_coder_or_analyst(
                state["plan_state"],
                state["agent_skill_level"],
                response.issue_skill_level,
            )

        return {
            "current_node": "router",
            "next_step": next_step,
            "issue_type": issue_type,
            "issue_skill_level": response.issue_skill_level,
            "issue_skill_level_reasoning": response.reasoning,
            "user_message": "",
            "working_state": "working...",
        }

    return router_node


def route_to_coder_or_analyst(
    plan_state: PlanState, agent_skill_level: str, issue_skill_level: str
) -> str:
    """Route the issue to coder or analyst."""
    if plan_state == PlanState.APPROVED:
        logger.info("Plan is approved, routing to coder")
        return "coder"

    # if the difficulty of the issue is higher than the agent's skill level, reject it
    if agent_skill_level == SkillLevelType.JUNIOR and issue_skill_level == SkillLevelType.SENIOR:
        logger.info("Issue difficulty is higher than agent skill level, rejecting")
        return "reject"

    # if the difficulty of the issue is lower to the agent's skill level,
    # and the issue can be executed by the coder without a plan, then route to coder
    if agent_skill_level == SkillLevelType.SENIOR and issue_skill_level == SkillLevelType.JUNIOR:
        logger.info("Issue difficulty is lower than agent skill level, routing to coder")
        return "coder"

    # if the difficulty of the issue is equal to the agent's skill level,
    # and the issue must be planned by the analyst, then route to analyst
    logger.info("Issue difficulty is equal to agent skill level, routing to analyst")
    return "analyst"
