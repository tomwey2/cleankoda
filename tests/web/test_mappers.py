"""Tests for web layer mappers."""

from __future__ import annotations

from app.core.models import AgentConfig, TaskSystem
from app.web.mappers.config_mapper import ConfigMapper
from app.web.schemas.settings_schema import (
    LLMConfigSchema,
    SettingsFormSchema,
    TrelloConfigSchema,
)


class TestConfigMapperSchemaToModel:
    """Tests for ConfigMapper.schema_to_model."""

    def test_applies_basic_fields(self, app):
        """Basic fields should be applied to model."""
        schema = SettingsFormSchema(
            task_system_type="TRELLO",
            agent_skill_level="senior",
            polling_interval_seconds=120,
            repo_type="GITHUB",
            github_repo_url="https://github.com/test/repo.git",
            is_active=True,
        )
        config = AgentConfig()

        result = ConfigMapper.schema_to_model(schema, config)

        assert result.task_system_type == "TRELLO"
        assert result.agent_skill_level == "senior"
        assert result.polling_interval_seconds == 120
        assert result.repo_type == "GITHUB"
        assert result.github_repo_url == "https://github.com/test/repo.git"
        assert result.is_active is True

    def test_applies_llm_config(self, app):
        """LLM config should be applied to model."""
        llm_config = LLMConfigSchema(
            provider="openai",
            model_large="gpt-4",
            model_small="gpt-3.5-turbo",
            temperature="0.7",
        )
        schema = SettingsFormSchema(llm_config=llm_config)
        config = AgentConfig()

        result = ConfigMapper.schema_to_model(schema, config)

        assert result.llm_provider == "openai"
        assert result.llm_model_large == "gpt-4"
        assert result.llm_model_small == "gpt-3.5-turbo"
        assert result.llm_temperature == "0.7"

    def test_applies_trello_config(self, app):
        """Trello config should be applied to model and task_system."""
        trello_config = TrelloConfigSchema(
            api_key="test-key",
            api_token="test-token",
            base_url="https://api.trello.com/1",
            board_id="board-123",
            backlog_list="list-1",
            readfrom_list="list-2",
            progress_list="list-3",
            moveto_list="list-4",
        )
        schema = SettingsFormSchema(
            task_system_type="TRELLO",
            trello_config=trello_config,
        )
        config = AgentConfig()

        result = ConfigMapper.schema_to_model(schema, config)

        assert result.task_backlog_state == "list-1"
        assert result.task_readfrom_state == "list-2"
        assert result.task_in_progress_state == "list-3"
        assert result.task_moveto_state == "list-4"
        assert result.task_system is not None
        assert result.task_system.api_key == "test-key"
        assert result.task_system.token == "test-token"
        assert result.task_system.board_id == "board-123"

    def test_creates_task_system_if_missing(self, app):
        """TaskSystem should be created if not present."""
        trello_config = TrelloConfigSchema(api_key="key")
        schema = SettingsFormSchema(
            task_system_type="TRELLO",
            trello_config=trello_config,
        )
        config = AgentConfig()
        assert config.task_system is None

        result = ConfigMapper.schema_to_model(schema, config)

        assert result.task_system is not None
        assert result.task_system.board_provider == "trello"

    def test_reuses_existing_task_system(self, app):
        """Existing TaskSystem should be reused."""
        existing_task_system = TaskSystem(
            task_system_type="TRELLO",
            board_provider="trello",
            board_id="old-board",
        )
        trello_config = TrelloConfigSchema(board_id="new-board")
        schema = SettingsFormSchema(
            task_system_type="TRELLO",
            trello_config=trello_config,
        )
        config = AgentConfig(task_system=existing_task_system)

        result = ConfigMapper.schema_to_model(schema, config)

        assert result.task_system is existing_task_system
        assert result.task_system.board_id == "new-board"


class TestConfigMapperModelToFormData:
    """Tests for ConfigMapper.model_to_form_data."""

    def test_extracts_basic_fields(self, app):
        """Basic fields should be extracted from model."""
        config = AgentConfig(
            agent_skill_level="junior",
            llm_provider="anthropic",
            llm_model_large="claude-3",
            llm_model_small="claude-instant",
            llm_temperature="0.5",
        )
        config.task_system = TaskSystem(
            board_provider="trello",
            api_key="key",
            token="token",
            board_id="board",
            base_url="https://api.trello.com/1",
        )

        result = ConfigMapper.model_to_form_data(config)

        assert result["agent_skill_level"] == "junior"
        assert result["llm_provider"] == "anthropic"
        assert result["llm_model_large"] == "claude-3"
        assert result["llm_model_small"] == "claude-instant"
        assert result["llm_temperature"] == "0.5"

    def test_extracts_trello_fields(self, app):
        """Trello fields should be extracted from model."""
        config = AgentConfig(
            task_backlog_state="backlog",
            task_readfrom_state="todo",
            task_in_progress_state="doing",
            task_moveto_state="done",
        )
        config.task_system = TaskSystem(
            board_provider="trello",
            api_key="api-key",
            token="api-token",
            board_id="board-id",
            base_url="https://api.trello.com/1",
        )

        result = ConfigMapper.model_to_form_data(config)

        assert result["trello_api_key"] == "api-key"
        assert result["trello_api_token"] == "api-token"
        assert result["trello_board_id"] == "board-id"
        assert result["trello_backlog_list"] == "backlog"
        assert result["trello_readfrom_list"] == "todo"
        assert result["trello_progress_list"] == "doing"
        assert result["trello_moveto_list"] == "done"

    def test_handles_missing_task_system(self, app):
        """Missing task_system should result in None values."""
        config = AgentConfig()
        config.task_system = None

        result = ConfigMapper.model_to_form_data(config)

        assert result["trello_api_key"] is None
        assert result["trello_api_token"] is None
        assert result["trello_board_id"] is None

    def test_defaults_llm_provider_to_mistral(self, app):
        """Missing llm_provider should default to mistral."""
        config = AgentConfig(llm_provider=None)
        config.task_system = TaskSystem(board_provider="trello")

        result = ConfigMapper.model_to_form_data(config)

        assert result["llm_provider"] == "mistral"


class TestConfigMapperFormToSchema:
    """Tests for ConfigMapper.form_to_schema."""

    def test_parses_trello_form_data(self, app):
        """Trello form data should be parsed into schema."""
        with app.test_request_context(
            "/settings",
            method="POST",
            data={
                "task_system_type": "TRELLO",
                "trello_api_key": "key",
                "trello_api_token": "token",
                "trello_board_id": "board",
                "trello_base_url": "https://api.trello.com/1",
                "trello_backlog_list": "backlog",
                "trello_readfrom_list": "todo",
                "trello_progress_list": "doing",
                "trello_moveto_list": "done",
                "llm_provider": "openai",
                "polling_interval_seconds": "90",
                "repo_type": "GITHUB",
                "github_repo_url": "https://github.com/test/repo.git",
            },
        ):
            result = ConfigMapper.form_to_schema()

            assert result.task_system_type == "TRELLO"
            assert result.trello_config is not None
            assert result.trello_config.api_key == "key"
            assert result.trello_config.api_token == "token"
            assert result.trello_config.board_id == "board"
            assert result.polling_interval_seconds == 90
            assert result.llm_config.provider == "openai"

    def test_parses_is_active_checkbox(self, app):
        """is_active checkbox should be parsed correctly."""
        with app.test_request_context(
            "/settings",
            method="POST",
            data={
                "task_system_type": "TRELLO",
                "is_active": "on",
            },
        ):
            result = ConfigMapper.form_to_schema()
            assert result.is_active is True

        with app.test_request_context(
            "/settings",
            method="POST",
            data={
                "task_system_type": "TRELLO",
            },
        ):
            result = ConfigMapper.form_to_schema()
            assert result.is_active is False
