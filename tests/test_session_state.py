import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cleankoda.config import AppConfig, get_config_file
from cleankoda.llm import CredentialsStore
from cleankoda.state import (
    AgentActivity,
    get_activity,
    get_session_state,
    set_activity,
    set_error_state,
)


class TestAppConfig(unittest.TestCase):

    def test_default_values(self):
        cfg = AppConfig()
        self.assertEqual(cfg.provider, "mistral")
        self.assertEqual(cfg.model, "mistral-small-latest")
        self.assertEqual(cfg.temperature, 0.2)
        self.assertEqual(cfg.max_tokens, 4096)
        self.assertFalse(hasattr(cfg, "api_keys"))

    def test_litellm_model_identifier(self):
        cfg = AppConfig(provider="ollama", model="llama3.3")
        self.assertEqual(cfg.litellm_model_identifier, "ollama/llama3.3")

        cfg = AppConfig(provider="anthropic", model="claude-3-5-sonnet-latest")
        self.assertEqual(cfg.litellm_model_identifier, "anthropic/claude-3-5-sonnet-latest")

        cfg = AppConfig(provider="google", model="gemini-2.5-flash")
        self.assertEqual(cfg.litellm_model_identifier, "gemini/gemini-2.5-flash")

        cfg = AppConfig(provider="openrouter", model="anthropic/claude-3")
        self.assertEqual(cfg.litellm_model_identifier, "anthropic/claude-3")

        cfg = AppConfig(provider="openai", model="gpt-4o")
        self.assertEqual(cfg.litellm_model_identifier, "openai/gpt-4o")

    def test_get_active_api_key_delegation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cred_file = Path(tmpdir) / "credentials.json"
            store = CredentialsStore(keys={"openai": "key_in_cred_store"})
            store.save(file_path=cred_file)

            cfg = AppConfig(provider="openai")

            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(cfg.get_active_api_key(credentials_file=cred_file), "key_in_cred_store")

            with patch.dict(os.environ, {"OPENAI_API_KEY": "key_in_env"}):
                self.assertEqual(cfg.get_active_api_key(credentials_file=cred_file), "key_in_env")

    def test_save_and_load_persistence_and_permissions(self):
        file_path = get_config_file()
        cfg = AppConfig(provider="anthropic", model="claude-3-5-haiku-latest", temperature=0.5)
        cfg.save()

        self.assertTrue(file_path.exists())

        # Permissions check 0o600
        file_stat = file_path.stat()
        file_mode = stat.S_IMODE(file_stat.st_mode)
        self.assertEqual(file_mode, 0o600)

        loaded_cfg = AppConfig.load()
        self.assertEqual(loaded_cfg.provider, "anthropic")
        self.assertEqual(loaded_cfg.model, "claude-3-5-haiku-latest")
        self.assertEqual(loaded_cfg.temperature, 0.5)


class TestSessionState(unittest.TestCase):

    def setUp(self):
        state = get_session_state()
        state.activity = AgentActivity.IDLE
        state.active_issue = None
        state.current_task_description = None
        state.last_error = None
        state.status_slots.clear()
        state._listeners.clear()

    def test_agent_activity_enum(self):
        self.assertEqual(AgentActivity.IDLE.value, "IDLE")
        self.assertEqual(AgentActivity.PLANNING.value, "PLANNING")
        self.assertEqual(AgentActivity.EXECUTING.value, "EXECUTING")
        self.assertEqual(AgentActivity.TESTING.value, "TESTING")
        self.assertEqual(AgentActivity.REVIEWING.value, "REVIEWING")
        self.assertEqual(AgentActivity.ERROR.value, "ERROR")

    def test_set_activity_and_notifications(self):
        notified = []

        def callback(s):
            notified.append(s.activity)

        get_session_state().subscribe(callback)
        set_activity(AgentActivity.PLANNING, "Task 1")

        self.assertEqual(get_activity(), AgentActivity.PLANNING)
        self.assertEqual(get_session_state().current_task_description, "Task 1")
        self.assertEqual(notified, [AgentActivity.PLANNING])

    def test_set_error_state(self):
        set_error_state("Failed to run command")
        self.assertEqual(get_activity(), AgentActivity.ERROR)
        self.assertEqual(get_session_state().last_error, "Failed to run command")

        set_activity(AgentActivity.IDLE)
        self.assertIsNone(get_session_state().last_error)


if __name__ == "__main__":
    unittest.main()
