"""
Defines the router node for the agent graph.

This node is responsible for the initial analysis of a task. It uses a
specialized LLM call to classify the user's request and decide which
specialist agent (e.g., Coder, Bugfixer, Analyst) should handle it next.
"""

import logging
from typing import Dict, Literal

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

from app.agent.services.message_processing import filter_messages_for_llm
from app.agent.state import AgentState, PlanState, TaskType
from app.agent.services.prompts import load_prompt
from app.core.db_task_utils import read_db_task
from app.core.models import Task

logger = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods
class RouterDecision(BaseModel):
    """Classify the incoming task into the correct category and skill level."""

    task_type: Literal["coding", "bugfixing", "analyzing"] = Field(
        description="The specific type of the task."
    )
    task_skill_level: Literal["junior", "senior"] = Field(
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
        system_message = load_prompt("systemprompt_router.md", state)
        # Router only needs the original task to make routing decision
        filtered_messages = filter_messages_for_llm(state["messages"], max_messages=3)
        base_messages = [SystemMessage(content=system_message)] + filtered_messages
        current_messages = list(base_messages)

        response = await structured_llm.ainvoke(current_messages)
        logger.info("Task type: %s", response.task_type)
        logger.info("Task skill level: %s", response.task_skill_level)
        logger.info("Task reasoning: %s", response.reasoning)

        task_type = TaskType.UNKNOWN
        if response.task_type in [t.value for t in TaskType]:
            task_type = TaskType(response.task_type)

        next_step = "reject"
        if task_type == TaskType.ANALYZING:
            next_step = "analyst"
        elif task_type == TaskType.BUGFIXING:
            next_step = "bugfixer"
        elif task_type == TaskType.CODING:
            next_step = route_to_coder_or_analyst(state, response)

        return {
            "next_step": next_step,
            "task_type": response.task_type,
            "task_skill_level": response.task_skill_level,
            "task_skill_level_reasoning": response.reasoning,
            "current_node": "router",
        }

    return router_node


def route_to_coder_or_analyst(state: AgentState, response: RouterDecision) -> str:
    if state["agent_skill_level"] == "junior" and response.task_skill_level == "senior":
        return "reject"

    db_task: Task | None = read_db_task()
    if db_task and db_task.plan_state == PlanState.APPROVED:
        return "coder"
    return "analyst"
