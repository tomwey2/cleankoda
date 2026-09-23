import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from cleankoda.commands.cmd_abort import cmd_abort
from cleankoda.commands.command_registry import CommandContext
from cleankoda.its import IssueState
from cleankoda.state import (
    ActiveIssueContext,
    AgentActivity,
    get_activity,
    get_session_state,
    set_active_issue,
    set_activity,
    set_status,
)


class TestCmdAbort(unittest.TestCase):

    def setUp(self):
        set_active_issue(None)
        state = get_session_state()
        state.activity = AgentActivity.IDLE
        state.status_slots.clear()

    def tearDown(self):
        set_active_issue(None)
        state = get_session_state()
        state.activity = AgentActivity.IDLE
        state.status_slots.clear()

    def test_abort_when_idle(self):
        ctx = CommandContext(memory=MagicMock())

        async def _test():
            res = await cmd_abort([], ctx)
            self.assertIn("Nothing to abort", res.output)
            self.assertEqual(get_activity(), AgentActivity.IDLE)

        asyncio.run(_test())

    def test_abort_when_reviewing_plan(self):
        issue = ActiveIssueContext(
            id="99", title="Plan Issue", description="Desc", state=IssueState.TODO
        )
        set_active_issue(issue)
        set_activity(AgentActivity.REVIEWING_PLAN, "Plan ready for review")
        set_status("action_hint", "Run '/execute' to start, type feedback to refine, or '/abort' to discard")

        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir)
            plans_dir = ws_path / ".cleankoda" / "plans"
            plans_dir.mkdir(parents=True, exist_ok=True)
            plan_file = plans_dir / "plan_plan-issue_99.md"
            plan_file.write_text("### Phase 1\n- [ ] Task", encoding="utf-8")

            mock_agent = MagicMock()
            mock_agent.sandbox.workspace = ws_path
            ctx = CommandContext(memory=MagicMock(), agent=mock_agent)

            async def _test():
                res = await cmd_abort([], ctx)
                self.assertIn("Plan discarded", res.output)
                self.assertEqual(get_activity(), AgentActivity.IDLE)
                self.assertFalse(plan_file.exists())
                self.assertNotIn("action_hint", get_session_state().status_slots)

            asyncio.run(_test())

    def test_abort_when_reviewing_code(self):
        set_activity(AgentActivity.REVIEWING_CODE, "Paused for review")
        set_status("action_hint", "Run '/execute' to continue")
        ctx = CommandContext(memory=MagicMock())

        async def _test():
            res = await cmd_abort([], ctx)
            self.assertIn("Execution paused", res.output)
            self.assertEqual(get_activity(), AgentActivity.IDLE)
            self.assertNotIn("action_hint", get_session_state().status_slots)

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
