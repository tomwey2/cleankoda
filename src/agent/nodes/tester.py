# pylint: disable=duplicate-code
"""
Defines the Tester agent node for the agent graph.

The Tester is a specialist agent responsible for verifying code changes,
running tests, and reporting the results.
"""

import logging
from typing import Any, Dict, Literal, Optional

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from src.agent.nodes.base import invoke_tool_node
from src.agent.services.prompts import load_prompt
from src.agent.services.summaries import append_agent_summary
from src.agent.state import AgentState

logger = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods
class TesterResult(BaseModel):
    """Call this tool ONLY when you have completed the testing process."""

    result: Literal["pass", "fail", "error"] = Field(
        ...,
        description=(
            "The final result. 'pass' if tests succeed, 'fail' if code has bugs "
            "that the coder can fix, 'error' if environmental/infrastructure "
            "issues prevent testing."
        ),
    )
    summary: str = Field(
        ...,
        description=(
            "A short summary of what happened (e.g. 'PR created at xyz', "
            "'Tests failed because of NPE', or 'Docker container not running')."
        ),
    )



def create_tester_node(llm, tools):
    """
    Factory function that creates the Tester agent node.

    Args:
        llm: The language model to be used by the tester.
        tools: A list of tools available to the tester.

    Returns:
        A function that represents the tester node.
    """

    def _llm_response_hook(state: AgentState, response: AIMessage) -> dict[str, Any]:
        """
        Hook function to process the LLM response and update the state.
        
        Args:
            state: The current agent state.
            response: The AIMessage response from the LLM.
            
        Returns:
            A dictionary containing the updated state.
        """
        summary_entries = list(state.get("agent_summary") or [])
        report_args = _get_report_result_args(response)
        if report_args:
            result = report_args.get("result", "unknown")
            summary = report_args.get("summary", "")
            logger.info("Test result: %s - %s", result.upper(), summary)
            summary_entries = append_agent_summary(summary_entries, "tester", summary)
        if summary_entries:
            return {"agent_summary": summary_entries}
        return {}

    async def tester_node(state: AgentState):
        if state["current_node"] != "tester":
            logger.info("--- TESTER node ---")

        system_message = load_prompt("systemprompt_tester.md", state)
        human_message = load_prompt("prompt_testing.md", state)

        return await invoke_tool_node(
            node_name="tester",
            state=state,
            llm=llm,
            tools=tools,
            system_prompt=system_message,
            human_prompt=human_message,
            max_messages=20,
            fallback_tool_name="report_test_result",
            fallback_tool_args={
                "result": "fail",
                "summary": "Testing could not complete due to invalid responses.",
            },
            llm_response_hook=_llm_response_hook,
        )

    return tester_node


def _get_report_result_args(response: Any) -> Optional[Dict[str, Any]]:
    """
    Returns the argument payload of the report_test_result tool call if present.
    """
    for tool_call in getattr(response, "tool_calls", []) or []:
        if tool_call.get("name") == "report_test_result":
            return tool_call.get("args", {})
    return None


def tests_passed(tool_args: Optional[Dict[str, Any]]) -> bool:
    """
    Determines whether the provided tool arguments represent a passing test run.
    """
    if not tool_args:
        return False
    result = tool_args.get("result")
    return isinstance(result, str) and result.lower() == "pass"
