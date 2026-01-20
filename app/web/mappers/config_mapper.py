"""Mappers for converting between web schemas and database models.

This module provides bidirectional mapping between:
- Web layer schemas (Pydantic models for form data)
- Database layer models (SQLAlchemy ORM models)
"""

from typing import Any, Dict

from flask import request

from app.core.models import AgentConfig, TaskSystem
from app.web.schemas.settings_schema import (
    JiraConfigSchema,
    LLMConfigSchema,
    SettingsFormSchema,
    TrelloConfigSchema,
)


class ConfigMapper:
    """Maps between web schemas and database models for configuration."""

    @staticmethod
    def form_to_schema() -> SettingsFormSchema:
        """Parse Flask form data into a validated SettingsFormSchema.

        Returns:
            SettingsFormSchema with validated form data.
        """
        task_system_type = request.form.get("task_system_type", "TRELLO")

        trello_config = None
        jira_config = None

        if task_system_type == "TRELLO":
            trello_config = TrelloConfigSchema(
                api_key=request.form.get("trello_api_key"),
                api_token=request.form.get("trello_api_token"),
                base_url=request.form.get(
                    "trello_base_url", "https://api.trello.com/1"
                ),
                board_id=request.form.get("trello_board_id"),
                backlog_list=request.form.get("trello_backlog_list"),
                readfrom_list=request.form.get("trello_readfrom_list"),
                progress_list=request.form.get("trello_progress_list"),
                moveto_list=request.form.get("trello_moveto_list"),
            )
        elif task_system_type == "JIRA":
            jira_config = JiraConfigSchema(
                username=request.form.get("jira_username"),
                api_token=request.form.get("jira_api_token"),
                jql_query=request.form.get("jira_jql_query"),
            )

        llm_config = LLMConfigSchema(
            provider=request.form.get("llm_provider"),
            model_large=request.form.get("llm_model_large"),
            model_small=request.form.get("llm_model_small"),
            temperature=request.form.get("llm_temperature"),
        )

        return SettingsFormSchema(
            task_system_type=task_system_type,
            agent_skill_level=request.form.get("agent_skill_level"),
            polling_interval_seconds=request.form.get("polling_interval_seconds"),
            repo_type=request.form.get("repo_type", "GITHUB"),
            github_repo_url=request.form.get("github_repo_url"),
            is_active="is_active" in request.form,
            trello_config=trello_config,
            jira_config=jira_config,
            llm_config=llm_config,
        )

    @staticmethod
    def schema_to_model(
        schema: SettingsFormSchema, config: AgentConfig
    ) -> AgentConfig:
        """Apply schema values to an AgentConfig model.

        Args:
            schema: Validated settings form schema.
            config: Existing AgentConfig to update (or new instance).

        Returns:
            Updated AgentConfig model (not yet committed).
        """
        config.task_system_type = schema.task_system_type
        config.agent_skill_level = schema.agent_skill_level
        config.polling_interval_seconds = schema.polling_interval_seconds
        config.repo_type = schema.repo_type
        config.github_repo_url = schema.github_repo_url
        config.is_active = schema.is_active

        ConfigMapper._apply_llm_config(schema.llm_config, config)

        if schema.task_system_type == "TRELLO" and schema.trello_config:
            ConfigMapper._apply_trello_config(schema.trello_config, config)

        return config

    @staticmethod
    def _apply_llm_config(llm_schema: LLMConfigSchema, config: AgentConfig) -> None:
        """Apply LLM configuration from schema to model."""
        config.llm_provider = llm_schema.provider
        config.llm_model_large = llm_schema.model_large
        config.llm_model_small = llm_schema.model_small
        config.llm_temperature = llm_schema.temperature

    @staticmethod
    def _apply_trello_config(
        trello_schema: TrelloConfigSchema, config: AgentConfig
    ) -> None:
        """Apply Trello configuration from schema to model."""
        config.task_backlog_state = trello_schema.backlog_list
        config.task_readfrom_state = trello_schema.readfrom_list
        config.task_in_progress_state = trello_schema.progress_list
        config.task_moveto_state = trello_schema.moveto_list

        task_system = ConfigMapper._get_or_create_task_system(config)
        task_system.board_provider = "trello"

        if trello_schema.board_id:
            task_system.board_id = trello_schema.board_id
        if trello_schema.api_key:
            task_system.api_key = trello_schema.api_key
        if trello_schema.api_token:
            task_system.token = trello_schema.api_token
        if trello_schema.base_url:
            task_system.base_url = trello_schema.base_url

    @staticmethod
    def _get_or_create_task_system(config: AgentConfig) -> TaskSystem:
        """Get existing TaskSystem or create a new one."""
        if config.task_system:
            return config.task_system

        task_system = TaskSystem(
            task_system_type=config.task_system_type,
            board_provider="trello",
        )
        config.task_system = task_system
        return task_system

    @staticmethod
    def model_to_form_data(config: AgentConfig) -> Dict[str, Any]:
        """Convert AgentConfig model to form data dictionary for template rendering.

        Args:
            config: AgentConfig model to convert.

        Returns:
            Dictionary suitable for populating the settings form template.
        """
        form_data: Dict[str, Any] = {
            "agent_skill_level": config.agent_skill_level,
            "llm_provider": config.llm_provider or "mistral",
            "llm_model_large": config.llm_model_large,
            "llm_model_small": config.llm_model_small,
            "llm_temperature": config.llm_temperature,
        }

        ConfigMapper._add_trello_form_data(config, form_data)
        ConfigMapper._add_jira_form_data(form_data)

        return form_data

    @staticmethod
    def _add_trello_form_data(config: AgentConfig, form_data: Dict[str, Any]) -> None:
        """Add Trello-specific fields to form data."""
        task_system = config.task_system
        if task_system:
            form_data["trello_api_key"] = task_system.api_key
            form_data["trello_api_token"] = task_system.token
            form_data["trello_board_id"] = task_system.board_id
            form_data["trello_base_url"] = task_system.base_url
        else:
            form_data["trello_api_key"] = None
            form_data["trello_api_token"] = None
            form_data["trello_board_id"] = None
            form_data["trello_base_url"] = None

        form_data["trello_backlog_list"] = config.task_backlog_state
        form_data["trello_readfrom_list"] = config.task_readfrom_state
        form_data["trello_progress_list"] = config.task_in_progress_state
        form_data["trello_moveto_list"] = config.task_moveto_state

    @staticmethod
    def _add_jira_form_data(form_data: Dict[str, Any]) -> None:
        """Add Jira-specific fields to form data (placeholder)."""
        form_data["jira_username"] = "JIRA_USERNAME"
        form_data["jira_api_token"] = "JIRA_API_TOKEN"
        form_data["jira_jql_query"] = "JIRA_JQL_QUERY"
