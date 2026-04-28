"""Service layer for settings management.

This module contains business logic for managing agent configuration settings,
separating concerns from the route handlers and database operations.
"""

import logging
from typing import Any, Dict

from src.core.extensions import db
from src.core.database.models import AgentSettingsDb
from src.core.services import credentials_service
from src.web.mappers import settings_mapper

logger = logging.getLogger(__name__)


def save_settings(agent_settings: AgentSettingsDb) -> AgentSettingsDb:
    """Save settings from validated schema to database.

    Args:
        schema: Validated settings form schema.
        settings: AgentSettings to update.

    Returns:
        Updated and persisted AgentSettings.
    """

    schema = settings_mapper.form_to_schema()
    settings_mapper.schema_to_model(schema, agent_settings)

    if agent_settings.llm_credential_id:
        cred = credentials_service.get_credential_by_id(agent_settings.llm_credential_id)
        if cred:
            agent_settings.llm_provider = cred.credential_type

    if not agent_settings.id:
        db.session.add(agent_settings)

    db.session.commit()
    logger.info("Settings saved for settings id=%s", agent_settings.id)
    return agent_settings


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
    llm_credential_types = [
        "MISTRAL",
        "GOOGLE",
        "OPENAI",
        "ANTHROPIC",
        "OLLAMA",
        "OPENROUTER",
        "GEMINI",
    ]
    llm_credentials = [c for c in all_credentials if c.credential_type in llm_credential_types]

    return {
        "settings": settings,
        "form_data": form_data,
        "selected_provider": selected_provider,
        "agent_image": agent_image,
        "trello_credentials": trello_credentials,
        "github_credentials": github_credentials,
        "llm_credentials": llm_credentials,
    }
