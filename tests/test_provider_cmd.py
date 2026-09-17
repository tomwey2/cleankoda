from cleankoda.memory import MemoryInFile
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import FloatContainer, Window
from prompt_toolkit.layout.layout import Layout

from cleankoda.commands import CommandContext, registry
from cleankoda.config import AppConfig, get_config_file
from cleankoda.llm import CredentialsStore
from cleankoda.memory import Memory


class TestProviderCommand(unittest.TestCase):

    def test_command_registered(self):
        cmds = registry.list_commands()
        cmd_names = {c.name for c in cmds}
        self.assertIn("provider", cmd_names)

    @patch("cleankoda.commands.cmd_provider.prompt_for_api_key_interactive", new_callable=AsyncMock)
    def test_provider_direct_argument_valid_ollama(self, mock_prompt_key):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryInFile(system_prompt="Test", file=Path(tmpdir) / "mem.json")
            ctx = CommandContext(memory=memory)

            res = registry.dispatch("/provider ollama", ctx)
            self.assertIn("Provider switched to: ollama", res.output)
            self.assertEqual(AppConfig.load().provider, "ollama")
            mock_prompt_key.assert_not_called()

    @patch("cleankoda.commands.cmd_provider.prompt_for_api_key_interactive", new_callable=AsyncMock)
    def test_provider_direct_argument_with_key_prompt(self, mock_prompt_key):
        mock_prompt_key.return_value = "sk-new-openai-key"
        with tempfile.TemporaryDirectory() as tmpdir:
            cred_file = Path(tmpdir) / "credentials.json"
            memory = MemoryInFile(system_prompt="Test", file=Path(tmpdir) / "mem.json")
            ctx = CommandContext(memory=memory)

            with patch("cleankoda.llm.credentials.DEFAULT_CREDENTIALS_FILE", cred_file):
                res = registry.dispatch("/provider openai", ctx)
                self.assertIn("API key updated. Provider switched to: openai", res.output)
                self.assertEqual(AppConfig.load().provider, "openai")
                self.assertEqual(CredentialsStore.load(file_path=cred_file).get_key("openai"), "sk-new-openai-key")

    def test_provider_direct_argument_invalid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryInFile(system_prompt="Test", file=Path(tmpdir) / "mem.json")
            ctx = CommandContext(memory=memory)

            res = registry.dispatch("/provider unknown_llm", ctx)
            self.assertIn("Invalid provider 'unknown_llm'", res.output)
            self.assertIn("Available providers:", res.output)
            self.assertFalse(get_config_file().exists())

    @patch("cleankoda.commands.cmd_provider.prompt_for_api_key_interactive", new_callable=AsyncMock)
    @patch("cleankoda.commands.cmd_provider.select_provider_interactive", new_callable=AsyncMock)
    def test_provider_interactive_selection(self, mock_select, mock_prompt_key):
        mock_select.return_value = "anthropic"
        mock_prompt_key.return_value = "sk-anthropic-123"

        with tempfile.TemporaryDirectory() as tmpdir:
            cred_file = Path(tmpdir) / "credentials.json"
            memory = MemoryInFile(system_prompt="Test", file=Path(tmpdir) / "mem.json")
            ctx = CommandContext(memory=memory)

            with patch("cleankoda.llm.credentials.DEFAULT_CREDENTIALS_FILE", cred_file):
                res = registry.dispatch("/provider", ctx)
                self.assertIn("API key updated. Provider switched to: anthropic", res.output)
                self.assertEqual(AppConfig.load().provider, "anthropic")
                mock_select.assert_called_once()
                mock_prompt_key.assert_called_once()

    @patch("cleankoda.commands.cmd_provider.select_provider_interactive", new_callable=AsyncMock)
    def test_provider_interactive_cancellation(self, mock_select):
        mock_select.return_value = None  # User pressed ESC
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryInFile(system_prompt="Test", file=Path(tmpdir) / "mem.json")
            ctx = CommandContext(memory=memory)

            res = registry.dispatch("/provider", ctx)
            self.assertIn("Provider selection cancelled.", res.output)
            self.assertFalse(get_config_file().exists())
            mock_select.assert_called_once()

    def test_show_tui_modal_provider_dialog(self):
        from cleankoda.commands.cmd_provider import _show_tui_modal_provider_dialog

        float_container = FloatContainer(content=Window(), floats=[])
        layout = Layout(float_container)
        app = Application(layout=layout)

        async def _test():
            task = asyncio.create_task(_show_tui_modal_provider_dialog(app, float_container, "openai"))
            await asyncio.sleep(0.01)

            self.assertEqual(len(float_container.floats), 1)

            dialog_hs = float_container.floats[0].content
            dialog_kb = dialog_hs.key_bindings
            dialog_kb.bindings[1].handler(None)

            res = await task
            self.assertEqual(res, "openai")
            self.assertEqual(len(float_container.floats), 0)

        asyncio.run(_test())

    def test_show_tui_modal_api_key_dialog(self):
        from cleankoda.commands.cmd_provider import _show_tui_modal_api_key_dialog

        float_container = FloatContainer(content=Window(), floats=[])
        layout = Layout(float_container)
        app = Application(layout=layout)

        async def _test():
            task = asyncio.create_task(_show_tui_modal_api_key_dialog(app, float_container, "openai", "Status text"))
            await asyncio.sleep(0.01)

            self.assertEqual(len(float_container.floats), 1)

            dialog_hs = float_container.floats[0].content
            dialog_hs.input_field.text = "secret-key-123"

            dialog_kb = dialog_hs.key_bindings
            dialog_kb.bindings[1].handler(None)  # Trigger enter

            res = await task
            self.assertEqual(res, "secret-key-123")
            self.assertEqual(len(float_container.floats), 0)

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
