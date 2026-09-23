import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from cleankoda.agent import Agent
from cleankoda.main import main, run_headless
from cleankoda.memory.memory_in_file import MemoryInFile
from cleankoda.sandbox import Sandbox
from cleankoda.tools import Bash, ListDir, ReadFile, WriteFile
from cleankoda.tui import TUI


class TestMainDualMode(unittest.TestCase):

    def test_run_headless_slash_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir)
            mem = MemoryInFile(system_prompt="Test", file=ws_path / "mem.json")
            sb = Sandbox(default_image_id=None, workspace=ws_path)
            tools = [
                ListDir(workspace=ws_path),
                ReadFile(workspace=ws_path),
                WriteFile(workspace=ws_path),
                Bash(sandbox=sb),
            ]
            agent = Agent(
                memory=mem,
                tools=tools,
                sandbox=sb,
            )
            captured_output = io.StringIO()
            with patch("sys.stdout", captured_output):
                run_headless(agent, "/help")
            output = captured_output.getvalue()
            self.assertIn("Available Commands:", output)
            self.assertIn("/exit", output)

    @patch("cleankoda.agent.Agent.run")
    def test_run_headless_agent_call(self, mock_agent_run):
        async def _mock_run_agent(*args, **kwargs):
            yield "Test response from agent"

        mock_agent_run.side_effect = _mock_run_agent

        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir)
            mem = MemoryInFile(system_prompt="Test", file=ws_path / "mem.json")
            sb = Sandbox(default_image_id=None, workspace=ws_path)
            tools = [
                ListDir(workspace=ws_path),
                ReadFile(workspace=ws_path),
                WriteFile(workspace=ws_path),
                Bash(sandbox=sb),
            ]
            agent = Agent(
                memory=mem,
                tools=tools,
                sandbox=sb,
            )
            captured_output = io.StringIO()
            with patch("sys.stdout", captured_output):
                run_headless(agent, "What is 1+1?")
            output = captured_output.getvalue()
            self.assertIn("Test response from agent", output)
            mock_agent_run.assert_called_once()

    @patch("cleankoda.main.run_headless")
    def test_main_with_positional_prompt(self, mock_run_headless):
        main(["Explain", "this", "code"])
        mock_run_headless.assert_called_once_with(ANY, "Explain this code")

    def setUp(self):
        from cleankoda.state import get_session_state, AgentActivity, clear_active_issue
        clear_active_issue()
        state = get_session_state()
        state.activity = AgentActivity.IDLE
        state.status_slots.clear()

    def tearDown(self):
        from cleankoda.state import get_session_state, AgentActivity, clear_active_issue
        clear_active_issue()
        state = get_session_state()
        state.activity = AgentActivity.IDLE
        state.status_slots.clear()

    @patch("cleankoda.main.run_tui")
    def test_main_with_tui_flag(self, mock_run_tui):
        main(["--tui"])
        mock_run_tui.assert_called_once_with(ANY)

    @patch("cleankoda.main.run_headless")
    def test_main_with_piped_input(self, mock_run_headless):
        with patch("sys.stdin.isatty", return_value=False):
            with patch("sys.stdin.read", return_value="Piped input prompt"):
                main([])
                mock_run_headless.assert_called_once_with(ANY, "Piped input prompt")

    def test_main_headless_missing_prompt_exits(self):
        with patch("sys.stdin.isatty", return_value=True):
            with patch("sys.stderr", io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    main(["--headless"])
                self.assertEqual(cm.exception.code, 1)

    def test_status_line_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir)
            mem = MemoryInFile(system_prompt="Test", file=ws_path / "mem.json")
            sb = Sandbox(default_image_id=None, workspace=ws_path)
            tools = [
                ListDir(workspace=ws_path),
                ReadFile(workspace=ws_path),
                WriteFile(workspace=ws_path),
                Bash(sandbox=sb),
            ]
            agent = Agent(memory=mem, tools=tools, sandbox=sb)
            tui = TUI(agent)
            tui.update_status_line()
            lines = tui.status_line.text.splitlines()
            self.assertGreaterEqual(len(lines), 2)
            self.assertIn("Model:", lines[0])
            self.assertEqual(lines[1], "Issue: [No active Issue]")
            self.assertEqual(tui.status_line.window.height, 2)

    @patch("cleankoda.main.run_tui")
    @patch("cleankoda.main.set_workspace")
    def test_main_workspace_valid(self, mock_set_workspace, mock_run_tui):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            main(["-ws", str(tmp_path), "--tui"])
            mock_set_workspace.assert_called_once_with(tmp_path.resolve())

    @patch("cleankoda.main.set_workspace")
    def test_main_workspace_invalid(self, mock_set_workspace):
        with tempfile.TemporaryDirectory() as tmpdir:
            non_existent = Path(tmpdir) / "does_not_exist"
            with patch("sys.stderr", io.StringIO()) as mock_stderr:
                with self.assertRaises(SystemExit) as cm:
                    main(["--workspace", str(non_existent), "--tui"])
                self.assertEqual(cm.exception.code, 1)
                self.assertIn("does not exist", mock_stderr.getvalue())
            mock_set_workspace.assert_not_called()

    @patch("cleankoda.main.run_tui")
    @patch("cleankoda.main.set_workspace")
    def test_main_workspace_default(self, mock_set_workspace, mock_run_tui):
        main(["--tui"])
        mock_set_workspace.assert_called_once_with(Path.cwd())


if __name__ == "__main__":
    unittest.main()
