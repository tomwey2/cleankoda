import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cleankoda.its import IssueState
from cleankoda.agent import Agent
from cleankoda.commands import CommandContext
from cleankoda.commands.cmd_plan import (
    cmd_plan,
    create_plan_headless,
    create_plan_with_tui,
    is_tool_call_display,
    sanitize_filename,
)
from cleankoda.memory import Memory
from cleankoda.state import (
    ActiveIssueContext,
    clear_active_issue,
    get_active_issue,
    set_active_issue,
)


class TestCmdPlanHelpers(unittest.TestCase):

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("Refactor Auth & Tokens!"), "refactor-auth-tokens")
        self.assertEqual(sanitize_filename("---test___file--"), "test-file")
        self.assertEqual(sanitize_filename("   "), "plan")

    def test_is_tool_call_display(self):
        registry_mock = MagicMock()
        registry_mock.get_schemas.return_value = [
            {"type": "function", "function": {"name": "read_file"}},
            {"type": "function", "function": {"name": "list_dir"}},
        ]
        self.assertTrue(is_tool_call_display("read_file(path='foo.py')", registry_mock))
        self.assertFalse(is_tool_call_display("This is normal output text.", registry_mock))


class TestCmdPlan(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        clear_active_issue()

    def tearDown(self):
        clear_active_issue()

    async def test_cmd_plan_without_issue_or_goal(self):
        memory = Memory()
        ctx = CommandContext(memory=memory)
        res = await cmd_plan([], ctx)

        self.assertIn("No active issue set and no goal specified", res.output)

    async def test_cmd_plan_with_goal_no_issue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir)
            memory = Memory()
            sandbox = MagicMock()
            sandbox.workspace = ws_path
            agent = Agent(memory=memory, tools=[], sandbox=sandbox)

            async def mock_stream(*args, **kwargs):
                yield "## Plan Title\n1. Step One\n2. Step Two"

            with patch.object(agent.llm_service, "stream_completion", side_effect=mock_stream):
                ctx = CommandContext(memory=memory, agent=agent)
                res = await cmd_plan(["Refactor", "database", "schema"], ctx)

            plans_dir = ws_path / ".cleankoda" / "plans"
            self.assertTrue(plans_dir.exists())
            target_file = plans_dir / "plan_refactor-database-schema.md"
            self.assertTrue(target_file.exists())
            file_content = target_file.read_text(encoding="utf-8")
            self.assertIn("## Plan Title", file_content)
            self.assertIn("1. Step One", file_content)

    async def test_cmd_plan_with_active_issue(self):
        issue = ActiveIssueContext(
            id="CARD-500",
            title="Implement User Profiles",
            description="Add profile page and avatar upload",
            state=IssueState.TODO,
        )
        set_active_issue(issue)

        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir)
            memory = Memory()
            sandbox = MagicMock()
            sandbox.workspace = ws_path
            agent = Agent(memory=memory, tools=[], sandbox=sandbox)

            async def mock_stream(*args, **kwargs):
                yield "## Profile Feature Plan\n- Architectural overview\n- Affected files"

            with patch.object(agent.llm_service, "stream_completion", side_effect=mock_stream):
                ctx = CommandContext(memory=memory, agent=agent)
                res = await cmd_plan([], ctx)

            plans_dir = ws_path / ".cleankoda" / "plans"
            self.assertTrue(plans_dir.exists())
            target_file = plans_dir / "plan_implement-user-profiles_CARD-500.md"
            self.assertTrue(target_file.exists())
            file_content = target_file.read_text(encoding="utf-8")
            self.assertIn("## Profile Feature Plan", file_content)

            user_msg = memory.messages[-1]
            self.assertIn("Active Ticket: #CARD-500 - Implement User Profiles", user_msg["content"])

    async def test_create_plan_headless(self):
        memory = Memory()
        sandbox = MagicMock()
        sandbox.workspace = Path("/tmp")
        agent = Agent(memory=memory, tools=[], sandbox=sandbox)

        async def mock_stream(*args, **kwargs):
            yield "Plan output content"

        with patch.object(agent.llm_service, "stream_completion", side_effect=mock_stream):
            chunks = await create_plan_headless(agent)

        self.assertEqual(chunks, ["Plan output content"])

    async def test_create_plan_with_tui(self):
        memory = Memory()
        sandbox = MagicMock()
        sandbox.workspace = Path("/tmp")
        agent = Agent(memory=memory, tools=[], sandbox=sandbox)

        tui_mock = MagicMock()
        tui_mock.history_area.text = ""
        tui_mock.cancel_event = None
        app_mock = MagicMock()
        app_mock.tui = tui_mock

        async def mock_stream(*args, **kwargs):
            yield "TUI Plan content"

        with patch.object(agent.llm_service, "stream_completion", side_effect=mock_stream):
            issue = ActiveIssueContext(id="1", title="Test", description="Desc", state=IssueState.TODO)
            chunks = await create_plan_with_tui(tui_mock, agent, issue, "goal")

        self.assertEqual(chunks, ["TUI Plan content"])
        self.assertIn("[Planer] Generating implementation plan", tui_mock.history_area.text)


if __name__ == "__main__":
    unittest.main()
