"""Runtime preparation helpers for the agent worker."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict

from langchain_core.language_models import BaseChatModel

from src.agent.services.git_workspace import ensure_repository_exists
from src.agent.services.llm_factory import get_llm
from src.agent.system_mappings import MCP_SYSTEM_DEFINITIONS
from src.agent.utils import get_workbench, get_workspace
from src.core.config import get_env_settings
from src.core.database.models import AgentSettingsDb
from src.core.types import AgentStack
from src.core.services import agent_settings_service, users_service
from src.core.extern.its.issue_tracking_system import IssueTrackingSystem
from src.core.extern.its.its_factory import create_its
from src.core.extern.vcs.version_control_system import VersionControlSystem
from src.core.extern.vcs.vcs_factory import create_vcs

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeSettings:
    """Aggregated runtime inputs required to execute one agent cycle."""

    agent_settings: AgentSettingsDb
    agent_stack: AgentStack
    mcp_system_def: Dict[str, Any]
    llm_large: BaseChatModel
    llm_small: BaseChatModel
    its: IssueTrackingSystem
    vcs: VersionControlSystem


def prepare_runtime() -> RuntimeSettings | None:
    """Build the runtime context needed by the agent worker."""
    user_id = users_service.get_current_user_id()
    agent_settings: AgentSettingsDb | None = agent_settings_service.get_or_create_agent_settings(
        user_id
    )
    if not agent_settings:
        return None

    logger.info(
        "Agent settings:\n%s",
        json.dumps(agent_settings.as_dict(), indent=2, default=str),
    )
    if not agent_settings.vcs_repo_url:
        logger.error("GitHub repository URL not provided.")
        return None

    logger.info("Workspace: %s", get_workspace())
    ensure_repository_exists(agent_settings.vcs_repo_url, get_workspace())

    if agent_settings.its_type not in MCP_SYSTEM_DEFINITIONS:
        logger.error("Issue tracking system '%s' not defined.", agent_settings.its_type)
        return None

    env_settings = get_env_settings()
    agent_stack = _resolve_agent_stack(env_settings.agent_stack)
    mcp_system_def = MCP_SYSTEM_DEFINITIONS[agent_settings.its_type]
    its = create_its(agent_settings)
    vcs = create_vcs(agent_settings)

    return RuntimeSettings(
        agent_settings=agent_settings,
        agent_stack=agent_stack,
        mcp_system_def=mcp_system_def,
        llm_large=get_llm(agent_settings, True),
        llm_small=get_llm(agent_settings, False),
        its=its,
        vcs=vcs,
    )


def _resolve_agent_stack(env_value: str | None) -> AgentStack:
    """Return the desired AgentStack from env or derive from workbench."""

    normalized = (env_value or "").strip().lower()
    if normalized == AgentStack.BACKEND:
        return AgentStack.BACKEND
    if normalized == AgentStack.FRONTEND:
        return AgentStack.FRONTEND
    if normalized == "gradle-node":
        return AgentStack.GRADLE_NODE

    workbench_name = get_workbench()
    derived_stack = (
        AgentStack.FRONTEND if workbench_name == "workbench-frontend" else AgentStack.BACKEND
    )
    logger.warning(
        "AGENT_STACK not provided or invalid; derived stack '%s' from workbench '%s'",
        derived_stack,
        workbench_name,
    )
    return derived_stack
