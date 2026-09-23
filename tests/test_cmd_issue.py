from litellm.llms.huggingface.embedding.handler import config
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from cleankoda.its import IssueState
from cleankoda.agent import Agent, SYSTEM_PROMPT
from cleankoda.commands import CommandContext
from cleankoda.commands.cmd_issue import cmd_issue
from cleankoda.memory import Memory
from cleankoda.state import (
    ActiveIssueContext,
    clear_active_issue,
    get_active_issue,
    set_active_issue,
)
from cleankoda.tui import TUI


class TestActiveIssueContext(unittest.TestCase):

    def setUp(self):
        clear_active_issue()

    def tearDown(self):
        clear_active_issue()

    def test_active_issue_dataclass_and_snippet(self):
        ctx = ActiveIssueContext(
            id="CARD-123",
            title="Refactor Authentication",
            description="Update OAuth flow and tokens",
            state=IssueState.TODO,
            url="https://trello.com/c/CARD-123",
        )
        self.assertEqual(ctx.id, "CARD-123")
        self.assertEqual(ctx.title, "Refactor Authentication")
        self.assertEqual(ctx.description, "Update OAuth flow and tokens")
        self.assertEqual(ctx.state, IssueState.TODO)
        self.assertEqual(ctx.url, "https://trello.com/c/CARD-123")

        snippet = ctx.to_system_prompt_snippet()
        self.assertIn("=== ACTIVE TICKET / USER STORY ===", snippet)
        self.assertIn("ID: CARD-123", snippet)
        self.assertIn("Title: Refactor Authentication", snippet)
        self.assertIn("State: IssueState.TODO", snippet)
        self.assertIn("Description & Criteria:\nUpdate OAuth flow and tokens", snippet)

    def test_global_active_issue_get_set_clear(self):
        self.assertIsNone(get_active_issue())
        issue = ActiveIssueContext(
            id="1", title="Test", description="Desc", state=IssueState.IN_PROGRESS,
        )
        set_active_issue(issue)
        self.assertEqual(get_active_issue(), issue)
        clear_active_issue()
        self.assertIsNone(get_active_issue())


class TestDynamicSystemPrompt(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        clear_active_issue()

    def tearDown(self):
        clear_active_issue()

    async def test_dynamic_system_prompt_without_active_issue(self):
        memory = Memory(system_prompt=SYSTEM_PROMPT)
        sandbox = MagicMock()
        agent = Agent(memory=memory, tools=[], sandbox=sandbox)

        async def mock_stream(*args, **kwargs):
            if False:
                yield ""

        with patch.object(agent.llm_service, "stream_completion", side_effect=mock_stream):
            async for _ in agent.run(max_tool_iterations=1):
                pass

        sys_msg = memory.messages[0]
        self.assertEqual(sys_msg["role"], "system")
        self.assertEqual(sys_msg["content"], SYSTEM_PROMPT)

    async def test_dynamic_system_prompt_with_active_issue(self):
        issue = ActiveIssueContext(
            id="CARD-42",
            title="Add Dark Mode",
            description="Enable theme toggle",
            state=IssueState.TODO,
        )
        set_active_issue(issue)

        memory = Memory(system_prompt=SYSTEM_PROMPT)
        sandbox = MagicMock()
        agent = Agent(memory=memory, tools=[], sandbox=sandbox)

        async def mock_stream(*args, **kwargs):
            if False:
                yield ""

        with patch.object(agent.llm_service, "stream_completion", side_effect=mock_stream):
            async for _ in agent.run(max_tool_iterations=1):
                pass

        sys_msg = memory.messages[0]
        self.assertEqual(sys_msg["role"], "system")
        self.assertIn(SYSTEM_PROMPT, sys_msg["content"])
        self.assertIn("ID: CARD-42", sys_msg["content"])
        self.assertIn("Title: Add Dark Mode", sys_msg["content"])


class TestCmdIssue(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        clear_active_issue()

    def tearDown(self):
        clear_active_issue()

    async def test_issue_show_empty(self):
        memory = Memory()
        ctx = CommandContext(memory=memory)
        res = await cmd_issue(["show"], ctx)
        self.assertIn("No active issue currently set", res.output)

    async def test_issue_show_with_active_issue(self):
        issue = ActiveIssueContext(
            id="456",
            title="Fix bug",
            description="Crash on startup",
            state=IssueState.IN_REVIEW,
            url="https://example.com/456",
        )
        set_active_issue(issue)

        memory = Memory()
        ctx = CommandContext(memory=memory)
        res = await cmd_issue(["show"], ctx)
        self.assertIn("[Active Issue]: #456 - Fix bug", res.output)
        self.assertIn("State: IssueState.IN_REVIEW", res.output)
        self.assertIn("https://example.com/456", res.output)
        self.assertIn("Crash on startup", res.output)

    async def test_issue_clear(self):
        issue = ActiveIssueContext(
            id="789", title="Task", description="Desc", state=IssueState.DONE
        )
        set_active_issue(issue)
        self.assertIsNotNone(get_active_issue())

        memory = Memory()
        ctx = CommandContext(memory=memory)
        res = await cmd_issue(["clear"], ctx)
        self.assertEqual("Active issue cleared.", res.output)
        self.assertIsNone(get_active_issue())

    @patch("cleankoda.commands.cmd_issue.connect_mcp_server")
    async def test_issue_with_id_arg(self, mock_connect):
        mock_stack = AsyncMock()
        mock_session = AsyncMock()

        mock_content = MagicMock()
        mock_content.text = json.dumps({
            "id": "CARD-99",
            "title": "Update Dependencies",
            "description": "Bump httpx version",
            "state_name": "Todo",
            "url": "https://trello.com/c/CARD-99",
        })
        mock_res = MagicMock()
        mock_res.content = [mock_content]
        mock_session.call_tool.return_value = mock_res
        mock_connect.return_value = (mock_stack, mock_session)

        memory = Memory()
        ctx = CommandContext(memory=memory)
        res = await cmd_issue(["CARD-99"], ctx)
        self.assertIn("Active issue set: #CARD-99 - Update Dependencies", res.output)

        active = get_active_issue()
        self.assertIsNotNone(active)
        self.assertEqual(active.id, "CARD-99")
        self.assertEqual(active.title, "Update Dependencies")
        self.assertEqual(active.description, "Bump httpx version")

    @patch("cleankoda.commands.cmd_issue.connect_mcp_server")
    async def test_issue_sync(self, mock_connect):
        issue = ActiveIssueContext(
            id="CARD-99",
            title="Old Title",
            description="Old Desc",
            state=IssueState.TODO,
        )
        set_active_issue(issue)

        mock_stack = AsyncMock()
        mock_session = AsyncMock()

        mock_content = MagicMock()
        mock_content.text = json.dumps({
            "id": "CARD-99",
            "title": "New Synced Title",
            "description": "Updated Desc",
            "state_name": "In Progress",
            "url": "https://trello.com/c/CARD-99",
        })
        mock_res = MagicMock()
        mock_res.content = [mock_content]
        mock_session.call_tool.return_value = mock_res
        mock_connect.return_value = (mock_stack, mock_session)

        memory = Memory()
        ctx = CommandContext(memory=memory)
        res = await cmd_issue(["sync"], ctx)
        self.assertIn("Active issue set: #CARD-99 - New Synced Title", res.output)

        active = get_active_issue()
        self.assertEqual(active.title, "New Synced Title")

    @patch("cleankoda.commands.cmd_issue.select_issue_interactive", return_value="CARD-1")
    @patch("cleankoda.commands.cmd_issue.connect_mcp_server")
    async def test_issue_interactive_list(self, mock_connect, mock_select):
        mock_stack = AsyncMock()
        mock_session = AsyncMock()

        mock_content_issues = MagicMock()
        mock_content_issues.text = "- [CARD-1] Interactive Title: Desc preview..."
        mock_res_issues = MagicMock()
        mock_res_issues.content = [mock_content_issues]

        mock_content_details = MagicMock()
        mock_content_details.text = json.dumps({
            "id": "CARD-1",
            "title": "Interactive Title",
            "description": "Full interactive desc",
            "state_name": "Todo",
        })
        mock_res_details = MagicMock()
        mock_res_details.content = [mock_content_details]

        mock_session.call_tool.side_effect = [mock_res_issues, mock_res_details]
        mock_connect.return_value = (mock_stack, mock_session)

        memory = Memory()
        ctx = CommandContext(memory=memory)
        res = await cmd_issue([], ctx)

        self.assertIn("Active issue set: #CARD-1 - Interactive Title", res.output)
        active = get_active_issue()
        self.assertEqual(active.id, "CARD-1")


class TestTUIIntegration(unittest.TestCase):

    def setUp(self):
        clear_active_issue()
        from cleankoda.state import get_session_state, AgentActivity
        state = get_session_state()
        state.activity = AgentActivity.IDLE
        state.status_slots.clear()

    def tearDown(self):
        clear_active_issue()
        from cleankoda.state import get_session_state, AgentActivity
        state = get_session_state()
        state.activity = AgentActivity.IDLE
        state.status_slots.clear()

    def test_tui_bottom_toolbar_text(self):
        memory = Memory()
        sandbox = MagicMock()
        sb_img = MagicMock()
        sb_img.id = "host"
        sandbox.get_sandbox_image.return_value = sb_img
        agent = Agent(memory=memory, tools=[], sandbox=sandbox)
        tui = TUI(agent)

        self.assertEqual(tui._get_status_line_2(), "Issue: [No active Issue]")
        self.assertIn("[No active Issue]", tui.status_line.text)

        issue = ActiveIssueContext(
            id="101", title="UI polish", description="Fix toolbar", state=IssueState.TODO
        )
        set_active_issue(issue)
        tui.update_status_line()

        self.assertEqual(tui._get_status_line_2(), "Issue: [#101 UI polish]")
        self.assertIn("Issue: [#101 UI polish]", tui.status_line.text)


if __name__ == "__main__":
    unittest.main()
