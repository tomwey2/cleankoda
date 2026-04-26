"""
Main worker module for the AI agent.

This module contains the core asynchronous function that executes a single agent cycle,
from fetching issues to running the graph.
"""

import logging
import sys
from contextlib import AsyncExitStack

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph

from src.agent.graph import create_workflow
from src.agent.mcp.adapter import McpServerClient
from src.agent.runtime import RuntimeSetting
from src.agent.services.graph_assets import save_graph_as_mermaid, save_graph_as_png
from src.agent.utils import get_workspace, save_state_to_instance
from src.core.config import get_env_settings
from src.agent.state import AgentState
from src.core.types import IssueStateType
from src.core.services.agent_states_service import (
    get_agent_state_by_id,
    update_agent_state,
    delete_agent_state,
)
from src.core.services.agent_actions_service import create_agent_action
from src.core.services.users_service import get_current_user_id

logger = logging.getLogger(__name__)


async def run_agent_cycle(runtime: RuntimeSetting) -> None:
    """Internal helper that orchestrates one graph execution."""
    async with AsyncExitStack() as stack:
        enable_mcp = get_env_settings().enable_mcp_servers

        if enable_mcp:
            git_mcp = McpServerClient(
                command=sys.executable,
                args=["-m", "mcp_server_git", "--repository", get_workspace()],
                env=None,  # Uses default os.environ.copy() in adapter
            )
            await stack.enter_async_context(git_mcp)

            if runtime.mcp_system_def["command"]:
                active_issue_system = runtime.agent_settings.get_active_issue_system()
                if active_issue_system:
                    issue_mcp = McpServerClient(
                        runtime.mcp_system_def["command"][0],
                        runtime.mcp_system_def["command"][1:],
                        env={
                            "TRELLO_API_KEY": active_issue_system.its_api_key,
                            "TRELLO_TOKEN": active_issue_system.its_token,
                            "TRELLO_BASE_URL": active_issue_system.its_base_url,
                        },
                    )
                    await stack.enter_async_context(issue_mcp)
                else:
                    logger.warning("No active issue tracking system found for MCP server startup")
        else:
            logger.info("Skipping MCP server startup (ENABLE_MCP_SERVERS is disabled)")

        workflow: StateGraph = create_workflow(runtime)

        app_graph = workflow.compile()
        save_graph_as_png(app_graph)
        save_graph_as_mermaid(app_graph)
        logger.info("Executing graph cycle...")

        input_state = AgentState.init_state(runtime)
        input_state = _restore_state_from_database(input_state)

        # Config for threa level persistence
        thread_config: RunnableConfig = {
            "configurable": {"thread_id": "1"},
            "recursion_limit": 500,
        }

        # stream_mode="values" gibt uns den kompletten State nach jedem Node zurück
        async for current_state in app_graph.astream(
            input_state, config=thread_config, stream_mode="values", context=runtime.agent_settings
        ):
            save_state_to_instance(current_state)
            if current_state["issue_id"]:
                _persist_state_to_database(current_state)

        logger.info("Finish graph cycle.")


def _persist_state_to_database(current_state: AgentState) -> None:
    user_id = get_current_user_id()
    if current_state["current_node"] == "issue_fetch" and current_state["issue_from_todo"]:
        # if the issue is taken from todo state then delete the it in the
        # database (if exist)
        delete_agent_state(user_id=user_id, issue_id=current_state["issue_id"])

    agent_state = update_agent_state(
        user_id=user_id,
        issue_id=current_state["issue_id"],
        issue_name=current_state["issue_name"],
        issue_description=current_state["issue_description"],
        issue_type=current_state["issue_type"],
        issue_state=current_state["issue_state"].value,
        issue_url=current_state["issue_url"],
        issue_skill_level=current_state["issue_skill_level"],
        issue_skill_level_reasoning=current_state["issue_skill_level_reasoning"],
        issue_is_active=current_state["issue_is_active"],
        repo_branch_name=current_state["repo_branch_name"],
        repo_pr_url=current_state["repo_pr_url"],
        plan_state=current_state["plan_state"],
        working_state=current_state["working_state"],
        user_message=current_state["user_message"],
    )
    create_agent_action(
        user_id=user_id,
        agent_state_id=agent_state.id,
        tool_calls=current_state["current_tool_calls"],
        node_name=current_state["current_node"],
    )


def _restore_state_from_database(state: AgentState) -> AgentState:
    user_id = get_current_user_id()
    agent_state = get_agent_state_by_id(user_id)  # get the current entry
    if agent_state:
        state["issue_id"] = agent_state.issue_id
        state["issue_name"] = agent_state.issue_name
        state["issue_description"] = agent_state.issue_description
        state["issue_type"] = agent_state.issue_type
        state["issue_state"] = IssueStateType.from_string(agent_state.issue_state)
        state["issue_url"] = agent_state.issue_url
        state["issue_skill_level"] = agent_state.issue_skill_level
        state["issue_skill_level_reasoning"] = agent_state.issue_skill_level_reasoning
        state["issue_is_active"] = agent_state.issue_is_active
        state["repo_branch_name"] = agent_state.repo_branch_name
        state["repo_pr_url"] = agent_state.repo_pr_url
        state["plan_content"] = agent_state.plan_content
        state["plan_state"] = agent_state.plan_state
        state["working_state"] = agent_state.working_state
        state["user_message"] = agent_state.user_message
    return state
