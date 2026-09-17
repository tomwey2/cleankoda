from cleankoda.memory.memory_in_file import MemoryInFile
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import FloatContainer, Window
from prompt_toolkit.layout.layout import Layout

from cleankoda.commands import CommandContext, registry
from cleankoda.config import AppConfig
from cleankoda.memory import Memory


class TestModelCommand(unittest.TestCase):

    def test_command_registered(self):
        cmds = registry.list_commands()
        cmd_names = {c.name for c in cmds}
        self.assertIn("model", cmd_names)

    def test_model_direct_argument(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryInFile(system_prompt="Test", file=Path(tmpdir) / "mem.json")
            ctx = CommandContext(memory=memory)

            res = registry.dispatch("/model gpt-4o", ctx)
            self.assertIn("Model switched to: gpt-4o", res.output)
            self.assertEqual(AppConfig.load().model, "gpt-4o")

    @patch("cleankoda.commands.cmd_model.select_model_interactive", new_callable=AsyncMock)
    def test_model_interactive_selection(self, mock_select):
        mock_select.return_value = "claude-3-5-sonnet-latest"
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryInFile(system_prompt="Test", file=Path(tmpdir) / "mem.json")
            ctx = CommandContext(memory=memory)

            res = registry.dispatch("/model", ctx)
            self.assertIn("Model switched to: claude-3-5-sonnet-latest", res.output)
            self.assertEqual(AppConfig.load().model, "claude-3-5-sonnet-latest")
            mock_select.assert_called_once()

    @patch("cleankoda.commands.cmd_model.select_model_interactive", new_callable=AsyncMock)
    def test_model_interactive_cancellation(self, mock_select):
        mock_select.return_value = None  # User pressed ESC
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryInFile(system_prompt="Test", file=Path(tmpdir) / "mem.json")
            ctx = CommandContext(memory=memory)

            res = registry.dispatch("/model", ctx)
            self.assertIn("Model selection cancelled.", res.output)
            mock_select.assert_called_once()

    def test_show_tui_modal_model_dialog(self):
        from cleankoda.commands.cmd_model import _show_tui_modal_model_dialog

        float_container = FloatContainer(content=Window(), floats=[])
        layout = Layout(float_container)
        app = Application(layout=layout)

        async def _test():
            task = asyncio.create_task(
                _show_tui_modal_model_dialog(
                    app, float_container, ["gpt-4o", "gpt-4o-mini"], "openai", "gpt-4o"
                )
            )
            await asyncio.sleep(0.01)

            self.assertEqual(len(float_container.floats), 1)

            # Trigger enter keybinding (index 1)
            dialog_hs = float_container.floats[0].content
            dialog_kb = dialog_hs.key_bindings
            dialog_kb.bindings[1].handler(None)

            res = await task
            self.assertEqual(res, "gpt-4o")
            self.assertEqual(len(float_container.floats), 0)

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
