import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cleankoda.commands.cmd_execute import cmd_execute, get_workspace_diff, should_request_review
from cleankoda.commands.command_registry import CommandContext
from cleankoda.its import IssueState
from cleankoda.state import ActiveIssueContext, AgentActivity, get_activity, set_active_issue


class TestCmdExecute(unittest.TestCase):

    def setUp(self):
        state = set_active_issue(None)
        from cleankoda.state import get_session_state, AgentActivity
        state = get_session_state()
        state.activity = AgentActivity.IDLE
        state.status_slots.clear()

    def tearDown(self):
        set_active_issue(None)
        from cleankoda.state import get_session_state, AgentActivity
        state = get_session_state()
        state.activity = AgentActivity.IDLE
        state.status_slots.clear()

    def test_execute_without_active_issue(self):
        ctx = CommandContext(memory=MagicMock())
        async def _test():
            res = await cmd_execute([], ctx)
            self.assertIn("No active issue set", res.output)
        asyncio.run(_test())

    def test_execute_plan_not_found(self):
        issue = ActiveIssueContext(
            id="42", title="Test Feature", description="Body", state=IssueState.TODO
        )
        set_active_issue(issue)

        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir)
            mock_agent = MagicMock()
            mock_agent.sandbox.workspace = ws_path
            ctx = CommandContext(memory=MagicMock(), agent=mock_agent)

            async def _test():
                res = await cmd_execute([], ctx)
                self.assertIn("No implementation plan found", res.output)
                self.assertIn("/plan", res.output)

            asyncio.run(_test())

    def test_execute_single_step(self):
        issue = ActiveIssueContext(
            id="101", title="Add Feature", description="Desc", state=IssueState.TODO
        )
        set_active_issue(issue)

        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir)
            plans_dir = ws_path / ".cleankoda" / "plans"
            plans_dir.mkdir(parents=True, exist_ok=True)
            plan_file = plans_dir / "plan_add-feature_101.md"
            plan_file.write_text(
                "### Phase 1\n- [ ] Task One\n- [ ] Task Two\n", encoding="utf-8"
            )

            mock_memory = MagicMock()
            mock_agent = MagicMock()
            mock_agent.sandbox.workspace = ws_path

            async def _fake_run(cancel_event=None):
                yield "Agent output chunk"

            mock_agent.run = _fake_run

            ctx = CommandContext(memory=mock_memory, agent=mock_agent)

            async def _test():
                res = await cmd_execute([], ctx)
                self.assertIn("Task 1 completed", res.output)
                self.assertIn("Next open task [2/2]: Task Two", res.output)
                self.assertEqual(get_activity(), AgentActivity.REVIEWING_CODE)

                content = plan_file.read_text(encoding="utf-8")
                self.assertIn("- [x] Task One", content)
                self.assertIn("- [ ] Task Two", content)

            asyncio.run(_test())

    def test_execute_all_steps(self):
        issue = ActiveIssueContext(
            id="102", title="Full Task", description="Desc", state=IssueState.TODO
        )
        set_active_issue(issue)

        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir)
            plans_dir = ws_path / ".cleankoda" / "plans"
            plans_dir.mkdir(parents=True, exist_ok=True)
            plan_file = plans_dir / "plan_full-task_102.md"
            plan_file.write_text(
                "### Phase 1\n- [ ] Step 1\n- [ ] Step 2\n", encoding="utf-8"
            )

            mock_memory = MagicMock()
            mock_agent = MagicMock()
            mock_agent.sandbox.workspace = ws_path

            async def _fake_run(cancel_event=None):
                yield "Done chunk"

            mock_agent.run = _fake_run

            ctx = CommandContext(memory=mock_memory, agent=mock_agent)

            async def _test():
                res = await cmd_execute(["all"], ctx)
                self.assertIn("All tasks in implementation plan completed!", res.output)
                self.assertEqual(get_activity(), AgentActivity.IDLE)

                content = plan_file.read_text(encoding="utf-8")
                self.assertIn("- [x] Step 1", content)
                self.assertIn("- [x] Step 2", content)

            asyncio.run(_test())

    def test_get_workspace_diff(self):
        mock_agent = MagicMock()
        mock_env = MagicMock()
        mock_agent.sandbox.current_env = mock_env

        mock_env.run = AsyncMock()
        mock_env.run.side_effect = [
            {"output": "M src/file.py"},
            {"output": "diff --git a/src/file.py b/src/file.py\n+new line"},
        ]

        async def _test():
            diff_text = await get_workspace_diff(mock_agent)
            self.assertIn("--- Git Status ---", diff_text)
            self.assertIn("M src/file.py", diff_text)
            self.assertIn("--- Git Diff ---", diff_text)
            self.assertIn("+new line", diff_text)

        asyncio.run(_test())

    def test_execute_phase_boundary_hitl_review(self):
        issue = ActiveIssueContext(
            id="104", title="HITL Feature", description="Desc", state=IssueState.TODO
        )
        set_active_issue(issue)

        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir)
            plans_dir = ws_path / ".cleankoda" / "plans"
            plans_dir.mkdir(parents=True, exist_ok=True)
            plan_file = plans_dir / "plan_hitl-feature_104.md"
            plan_file.write_text(
                "### Phase 1: Unit Tests (Red Phase)\n"
                "- [ ] Write red test\n\n"
                "### Phase 2: Implementation (Green Phase)\n"
                "- [ ] Implement code\n",
                encoding="utf-8",
            )

            mock_memory = MagicMock()
            mock_agent = MagicMock()
            mock_agent.sandbox.workspace = ws_path
            mock_env = MagicMock()
            mock_agent.sandbox.current_env = mock_env
            mock_env.run = AsyncMock(side_effect=[
                {"output": "M tests/test_red.py"},
                {"output": "+def test_red(): pass"},
            ])

            async def _fake_run(cancel_event=None):
                yield "Agent code step"

            mock_agent.run = _fake_run
            ctx = CommandContext(memory=mock_memory, agent=mock_agent)

            async def _test():
                res = await cmd_execute(["all"], ctx)
                self.assertIn("Execution paused for review at milestone 'Phase 1: Unit Tests (Red Phase)'", res.output)
                self.assertEqual(get_activity(), AgentActivity.REVIEWING_CODE)

                content = plan_file.read_text(encoding="utf-8")
                self.assertIn("- [x] Write red test", content)
                self.assertIn("- [ ] Implement code", content)

            asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
