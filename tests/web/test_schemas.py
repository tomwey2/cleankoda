"""Tests for web layer Pydantic schemas."""

from __future__ import annotations

from app.web.schemas.settings_schema import (
    JiraConfigSchema,
    LLMConfigSchema,
    SettingsFormSchema,
    TrelloConfigSchema,
)


class TestTrelloConfigSchema:
    """Tests for TrelloConfigSchema validation."""

    def test_empty_strings_converted_to_none(self):
        """Empty strings should be converted to None."""
        schema = TrelloConfigSchema(
            api_key="",
            api_token="",
            board_id="",
        )
        assert schema.api_key is None
        assert schema.api_token is None
        assert schema.board_id is None

    def test_valid_values_preserved(self):
        """Valid string values should be preserved."""
        schema = TrelloConfigSchema(
            api_key="test-key",
            api_token="test-token",
            board_id="board-123",
            backlog_list="list-1",
            readfrom_list="list-2",
            progress_list="list-3",
            moveto_list="list-4",
        )
        assert schema.api_key == "test-key"
        assert schema.api_token == "test-token"
        assert schema.board_id == "board-123"
        assert schema.backlog_list == "list-1"

    def test_default_base_url(self):
        """Base URL should default to Trello API."""
        schema = TrelloConfigSchema()
        assert schema.base_url == "https://api.trello.com/1"


class TestLLMConfigSchema:
    """Tests for LLMConfigSchema validation."""

    def test_default_provider(self):
        """Provider should default to mistral."""
        schema = LLMConfigSchema()
        assert schema.provider == "mistral"

    def test_empty_provider_defaults_to_mistral(self):
        """Empty provider string should default to mistral."""
        schema = LLMConfigSchema(provider="")
        assert schema.provider == "mistral"

    def test_valid_provider_preserved(self):
        """Valid provider should be preserved."""
        schema = LLMConfigSchema(provider="openai")
        assert schema.provider == "openai"

    def test_empty_model_strings_to_none(self):
        """Empty model strings should be converted to None."""
        schema = LLMConfigSchema(
            model_large="",
            model_small="",
            temperature="",
        )
        assert schema.model_large is None
        assert schema.model_small is None
        assert schema.temperature is None


class TestSettingsFormSchema:
    """Tests for SettingsFormSchema validation."""

    def test_default_values(self):
        """Schema should have sensible defaults."""
        schema = SettingsFormSchema()
        assert schema.task_system_type == "TRELLO"
        assert schema.polling_interval_seconds == 60
        assert schema.repo_type == "GITHUB"
        assert schema.is_active is False

    def test_polling_interval_parsing(self):
        """Polling interval should be parsed from string."""
        schema = SettingsFormSchema(polling_interval_seconds="120")
        assert schema.polling_interval_seconds == 120

    def test_polling_interval_invalid_defaults_to_60(self):
        """Invalid polling interval should default to 60."""
        schema = SettingsFormSchema(polling_interval_seconds="invalid")
        assert schema.polling_interval_seconds == 60

    def test_polling_interval_empty_defaults_to_60(self):
        """Empty polling interval should default to 60."""
        schema = SettingsFormSchema(polling_interval_seconds="")
        assert schema.polling_interval_seconds == 60

    def test_is_active_from_string(self):
        """is_active should parse various truthy strings."""
        assert SettingsFormSchema(is_active="true").is_active is True
        assert SettingsFormSchema(is_active="1").is_active is True
        assert SettingsFormSchema(is_active="on").is_active is True
        assert SettingsFormSchema(is_active="yes").is_active is True
        assert SettingsFormSchema(is_active="false").is_active is False
        assert SettingsFormSchema(is_active="0").is_active is False

    def test_is_active_from_bool(self):
        """is_active should accept boolean values."""
        assert SettingsFormSchema(is_active=True).is_active is True
        assert SettingsFormSchema(is_active=False).is_active is False

    def test_nested_trello_config(self):
        """Schema should accept nested Trello config."""
        trello = TrelloConfigSchema(api_key="key", board_id="board")
        schema = SettingsFormSchema(trello_config=trello)
        assert schema.trello_config is not None
        assert schema.trello_config.api_key == "key"

    def test_nested_llm_config_defaults(self):
        """LLM config should have defaults when not provided."""
        schema = SettingsFormSchema()
        assert schema.llm_config is not None
        assert schema.llm_config.provider == "mistral"


class TestJiraConfigSchema:
    """Tests for JiraConfigSchema validation."""

    def test_empty_strings_converted_to_none(self):
        """Empty strings should be converted to None."""
        schema = JiraConfigSchema(
            username="",
            api_token="",
            jql_query="",
        )
        assert schema.username is None
        assert schema.api_token is None
        assert schema.jql_query is None

    def test_valid_values_preserved(self):
        """Valid string values should be preserved."""
        schema = JiraConfigSchema(
            username="user@example.com",
            api_token="token-123",
            jql_query="project = TEST",
        )
        assert schema.username == "user@example.com"
        assert schema.api_token == "token-123"
        assert schema.jql_query == "project = TEST"
