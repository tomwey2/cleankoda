"""Service layer for settings management.

This module contains business logic for managing agent configuration settings,
separating concerns from the route handlers and database operations.
"""

import logging
from typing import Any, Dict, Optional

from src.core.its.github_client import get_project_id_sync
from src.core.config import get_env_settings
from src.core.constants import LLM_PROVIDER_API_ENV
from src.core.extensions import db
from src.core.database.models import AgentSettingsDb
from src.core.services import credentials_service
from src.web.mappers import settings_mapper
from src.web.schemas.settings_schema import SettingsFormSchema
from src.core.types import IssueTrackingSystemType

logger = logging.getLogger(__name__)


def save_settings(agent_settings: AgentSettingsDb) -> AgentSettingsDb:
    """Save settings from validated schema to database.

    Args:
        schema: Validated settings form schema.
        settings: AgentSettings to update.

    Returns:
        Updated and persisted AgentSettings.

    Raises:
        ValueError: If GitHub project ID cannot be fetched.
    """

    schema = settings_mapper.form_to_schema()
    settings_mapper.schema_to_model(schema, agent_settings)

    is_github_issue_system = schema.its_type == IssueTrackingSystemType.GITHUB
    if is_github_issue_system and schema.its_config:
        _fetch_github_project_id(schema, agent_settings)

    if not agent_settings.id:
        db.session.add(agent_settings)

    db.session.commit()
    logger.info("Settings saved for settings id=%s", agent_settings.id)
    return agent_settings


def _fetch_github_project_id(schema: SettingsFormSchema, setting: AgentSettingsDb) -> None:
    """Fetch and store GitHub project ID if owner and number are provided.

    Args:
        schema: The validated settings form schema.
        setting: The AgentSettings to update.

    Raises:
        ValueError: If project cannot be found or API call fails.
    """
    github_config = schema.github_config
    if not github_config:
        return

    project_owner = github_config.project_owner
    project_number = github_config.project_number

    if not project_owner or project_number is None:
        logger.info("GitHub project owner or number not provided, skipping ID fetch")
        return

    base_url = github_config.base_url or "https://api.github.com"

    logger.info(
        "Fetching GitHub project ID for owner=%s, number=%s",
        project_owner,
        project_number,
    )

    github_issue_system = setting.get_its_type(IssueTrackingSystemType.GITHUB)
    if github_issue_system:
        # Reset the stored board id before attempting to fetch a new one
        github_issue_system.board_id = None

    try:
        api_token = github_config.api_token
        project_id = get_project_id_sync(project_owner, project_number, base_url, api_token)
        if github_issue_system:
            github_issue_system.board_id = project_id
            logger.info("GitHub project ID fetched and stored: %s", project_id)
    except RuntimeError as e:
        logger.error("Failed to fetch GitHub project ID: %s", e)
        raise ValueError(
            "Failed to fetch GitHub project ID. "
            "The stored Project ID has been cleared. "
            "Please verify the project owner, project number, and API token are correct."
        ) from e


def get_form_data(setting: AgentSettingsDb) -> Dict[str, Any]:
    """Get form data dictionary for template rendering.

    Args:
        setting: AgentSettings to convert.

    Returns:
        Dictionary suitable for populating the settings form.
    """
    return settings_mapper.model_to_form_data(setting)


def get_template_context(settings: AgentSettingsDb) -> Dict[str, Any]:
    """Build complete template context for settings page.

    Args:
        setting: AgentSettings model.

    Returns:
        Dictionary with all template variables.
    """
    form_data = get_form_data(settings)
    selected_provider = form_data.get("llm_provider", "mistral")

    missing_env = _check_missing_provider_env(selected_provider)
    show_ollama_warning = selected_provider == "ollama" and not get_env_settings().ollama_api_key

    if not settings.repo_url:
        settings.repo_url = get_env_settings().github_repo_url

    agent_age = "junior"
    if settings.agent_skill_level:
        agent_age = settings.agent_skill_level.lower()
    agent_gender = "male"
    if settings.agent_gender:
        agent_gender = settings.agent_gender.lower()
    agent_image = f"{agent_age}-{agent_gender}-is-waiting.png"

    all_credentials = credentials_service.get_credentials_for_user(settings.user_id)
    trello_credentials = [c for c in all_credentials if c.credential_type == "TRELLO"]
    github_credentials = [c for c in all_credentials if c.credential_type == "GITHUB"]

    return {
        "settings": settings,
        "form_data": form_data,
        "selected_provider": selected_provider,
        "missing_provider_env": missing_env,
        "show_ollama_warning": show_ollama_warning,
        "agent_image": agent_image,
        "trello_credentials": trello_credentials,
        "github_credentials": github_credentials,
    }


def _check_missing_provider_env(provider: str) -> Optional[str]:
    """Check if required environment variable is missing for provider.

    Args:
        provider: LLM provider name.

    Returns:
        Name of missing env var, or None if present/not required.
    """
    if provider == "ollama":
        return None

    env_name = LLM_PROVIDER_API_ENV.get(provider)
    if not env_name:
        return None

    if get_env_settings().get_api_key(env_name):
        return None

    return env_name
