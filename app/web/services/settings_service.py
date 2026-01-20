"""Service layer for settings management.

This module contains business logic for managing agent configuration settings,
separating concerns from the route handlers and database operations.
"""

import logging
import os
from typing import Any, Dict, Optional, Tuple

from app.core.constants import LLM_PROVIDER_API_ENV
from app.core.extensions import db
from app.core.models import AgentConfig, TaskSystem
from app.web.mappers.config_mapper import ConfigMapper
from app.web.schemas.settings_schema import SettingsFormSchema

logger = logging.getLogger(__name__)


class SettingsService:
    """Service for managing agent configuration settings."""

    @staticmethod
    def get_or_create_config() -> AgentConfig:
        """Retrieve existing config or create a new one with defaults.

        Returns:
            AgentConfig instance (may be transient if newly created).
        """
        config = AgentConfig.query.first()
        if not config:
            task_system = TaskSystem(
                task_system_type="TRELLO",
                board_provider="trello",
            )
            config = AgentConfig(task_system_type="TRELLO", task_system=task_system)
        return config

    @staticmethod
    def save_settings(schema: SettingsFormSchema, config: AgentConfig) -> AgentConfig:
        """Save settings from validated schema to database.

        Args:
            schema: Validated settings form schema.
            config: AgentConfig to update.

        Returns:
            Updated and persisted AgentConfig.
        """
        ConfigMapper.schema_to_model(schema, config)

        if not config.id:
            db.session.add(config)

        db.session.commit()
        logger.info("Settings saved for config id=%s", config.id)
        return config

    @staticmethod
    def get_form_data(config: AgentConfig) -> Dict[str, Any]:
        """Get form data dictionary for template rendering.

        Args:
            config: AgentConfig to convert.

        Returns:
            Dictionary suitable for populating the settings form.
        """
        return ConfigMapper.model_to_form_data(config)

    @staticmethod
    def get_template_context(config: AgentConfig) -> Dict[str, Any]:
        """Build complete template context for settings page.

        Args:
            config: AgentConfig model.

        Returns:
            Dictionary with all template variables.
        """
        form_data = SettingsService.get_form_data(config)
        selected_provider = form_data.get("llm_provider", "mistral")

        missing_env = SettingsService._check_missing_provider_env(selected_provider)
        show_ollama_warning = (
            selected_provider == "ollama"
            and not os.environ.get("OLLAMA_API_KEY")
        )

        if not config.github_repo_url:
            config.github_repo_url = os.environ.get("GITHUB_REPO_URL", "")

        return {
            "config": config,
            "form_data": form_data,
            "selected_provider": selected_provider,
            "missing_provider_env": missing_env,
            "show_ollama_warning": show_ollama_warning,
        }

    @staticmethod
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

        if os.environ.get(env_name):
            return None

        return env_name

    @staticmethod
    def validate_and_save(config: AgentConfig) -> Tuple[bool, Optional[str]]:
        """Validate form data and save settings.

        Args:
            config: AgentConfig to update.

        Returns:
            Tuple of (success, error_message).
        """
        try:
            schema = ConfigMapper.form_to_schema()
            SettingsService.save_settings(schema, config)
            return True, None
        except ValueError as e:
            logger.warning("Validation error saving settings: %s", e)
            return False, str(e)
