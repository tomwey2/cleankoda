"""Runtime preparation helpers for the agent worker."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from langchain_core.language_models import BaseChatModel

from src.agent.services.git_workspace import ensure_repository_exists
from src.agent.services.llm_factory import get_llm
from src.agent.system_mappings import MCP_SYSTEM_DEFINITIONS
from src.agent.utils import get_workbench, get_workspace
from src.core.config import get_env_settings
from src.core.database.models import AgentSettingsDb
from src.core.types import AgentStack

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeSetting:
    """Aggregated runtime inputs required to execute one agent cycle."""

    agent_settings: AgentSettingsDb
    agent_stack: AgentStack
    mcp_system_def: Dict[str, Any]
    llm_large: BaseChatModel
    llm_small: BaseChatModel


def prepare_runtime() -> Optional[RuntimeSetting]:
    """Build the runtime context needed by the agent worker."""
    settings: AgentSettingsDb | None = _get_agent_settings()
    if not settings:
        return None

    logger.info(
        "Agent settings:\n%s",
        json.dumps(settings.as_dict(), indent=2, default=str),
    )
    if not settings.repo_url:
        logger.error("GitHub repository URL not provided.")
        return None

    logger.info("Workspace: %s", get_workspace())
    ensure_repository_exists(settings.repo_url, get_workspace())

    if settings.its_type not in MCP_SYSTEM_DEFINITIONS:
        logger.error("Issue tracking system '%s' not defined.", settings.its_type)
        return None

    env_settings = get_env_settings()
    agent_stack = _resolve_agent_stack(env_settings.agent_stack)
    mcp_system_def = MCP_SYSTEM_DEFINITIONS[settings.its_type]

    return RuntimeSetting(
        agent_settings=settings,
        agent_stack=agent_stack,
        mcp_system_def=mcp_system_def,
        llm_large=get_llm(settings, True),
        llm_small=get_llm(settings, False),
    )


def _get_agent_settings() -> Optional[AgentSettingsDb]:
    """Load the active agent settings from the database."""
    settings = AgentSettingsDb.query.first()
    return settings


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
