import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cleankoda.commands.cmd_execute import cmd_execute, should_pause_for_review
from cleankoda.commands.command_registry import CommandContext
from cleankoda.its import IssueState
from cleankoda.state import ActiveIssueContext, set_active_issue


class TestCmdExecute(unittest.TestCase):

    def setUp(self):
        set_active_issue(None)

    def tearDown(self):
        set_active_issue(None)

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

                content = plan_file.read_text(encoding="utf-8")
                self.assertIn("- [x] Step 1", content)
                self.assertIn("- [x] Step 2", content)

            asyncio.run(_test())

    @patch("cleankoda.commands.cmd_execute.should_pause_for_review")
    def test_execute_review_pause(self, mock_pause):
        issue = ActiveIssueContext(
            id="103", title="Pause Test", description="Desc", state=IssueState.TODO
        )
        set_active_issue(issue)

        # Pause before second task
        mock_pause.side_effect = lambda prev, next_task: next_task is not None and next_task.index == 1

        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir)
            plans_dir = ws_path / ".cleankoda" / "plans"
            plans_dir.mkdir(parents=True, exist_ok=True)
            plan_file = plans_dir / "plan_pause-test_103.md"
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
                self.assertIn("Task 1 completed. Next open task [2/2]: Step 2", res.output)

                content = plan_file.read_text(encoding="utf-8")
                self.assertIn("- [x] Step 1", content)
                self.assertIn("- [ ] Step 2", content)

            asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
