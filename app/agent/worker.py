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

from app.core.constants import TECH_STACKS
from app.agent.graph import create_workflow
from app.agent.mcp.adapter import McpServerClient
from app.agent.runtime import RuntimeSetting
from app.agent.services.graph_assets import save_graph_as_mermaid, save_graph_as_png
from app.agent.utils import get_workspace, save_state_to_instance
from app.core.config import get_env_settings
from app.core.localdb.agent_issues_utils import (
    update_db_agent_state,
    read_db_agent_state,
    delete_db_agent_state,
)
from app.core.localdb.agent_actions_utils import create_db_agent_action

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

        inputs = {
            # values that are stored in the database
            "issue_id": None,
            "issue_name": None,
            "issue_description": None,
            "issue_comments": [],
            "issue_type": None,
            "issue_skill_level": None,
            "issue_skill_level_reasoning": None,
            "issue_from_todo": None,
            "repo_branch_name": None,
            "plan_content": None,
            "plan_state": None,
            "working_state": None,
            "user_message": None,
            # values that are not stored in the database
            "messages": [],
            "next_step": "",
            "agent_stack": runtime.agent_stack,
            "agent_skill_level": runtime.agent_settings.agent_skill_level,
            "current_node": None,
            "current_tool_calls": [],
            "prompt": None,
            "system_prompt": None,
            "tech_stack": TECH_STACKS[runtime.agent_stack],
        }

        db_agent_state = read_db_agent_state()
        if db_agent_state:
            inputs["issue_id"] = db_agent_state.issue_id
            inputs["issue_name"] = db_agent_state.issue_name
            inputs["issue_description"] = db_agent_state.issue_description
            inputs["issue_type"] = db_agent_state.issue_type
            inputs["issue_skill_level"] = db_agent_state.issue_skill_level
            inputs["issue_skill_level_reasoning"] = db_agent_state.issue_skill_level_reasoning
            inputs["repo_branch_name"] = db_agent_state.repo_branch_name
            inputs["plan_content"] = db_agent_state.plan_content
            inputs["plan_state"] = db_agent_state.plan_state
            inputs["working_state"] = db_agent_state.working_state
            inputs["user_message"] = db_agent_state.user_message

        # Config for threa level persistence
        thread_config: RunnableConfig = {
            "configurable": {"thread_id": "1"},
            "recursion_limit": 500,
        }

        # stream_mode="values" gibt uns den kompletten State nach jedem Node zurück
        async for current_state in app_graph.astream(
            inputs, config=thread_config, stream_mode="values", context=runtime.agent_settings
        ):
            save_state_to_instance(current_state)
            if current_state["issue_id"]:
                if (
                    current_state["current_node"] == "issue_fetch"
                    and current_state["issue_from_todo"]
                ):
                    # if the issue is taken from todo state then delete the it in the database (if exist)
                    delete_db_agent_state(current_state["issue_id"])

                db_agent_state = update_db_agent_state(
                    issue_id=current_state["issue_id"],
                    issue_name=current_state["issue_name"],
                    issue_description=current_state["issue_description"],
                    issue_type=current_state["issue_type"],
                    issue_skill_level=current_state["issue_skill_level"],
                    issue_skill_level_reasoning=current_state["issue_skill_level_reasoning"],
                    repo_branch_name=current_state["repo_branch_name"],
                    plan_state=current_state["plan_state"],
                    working_state=current_state["working_state"],
                    user_message=current_state["user_message"],
                )
                create_db_agent_action(
                    db_agent_state_id=db_agent_state.id,
                    tool_calls=current_state["current_tool_calls"],
                    current_node=current_state["current_node"],
                )

        logger.info("Finish graph cycle.")
