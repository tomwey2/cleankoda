import tempfile
import unittest
from pathlib import Path

from cleankoda.plans.manager import PlanManager, PlanTask


class TestPlanManager(unittest.TestCase):

    def test_nonexistent_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "nonexistent.md"
            mgr = PlanManager(plan_path)
            self.assertFalse(mgr.exists())
            self.assertEqual(mgr.read_content(), "")
            self.assertEqual(mgr.get_tasks(), [])
            self.assertIsNone(mgr.get_next_task())
            fake_task = PlanTask(
                index=0, line_number=1, phase="General", description="Test", completed=False
            )
            self.assertFalse(mgr.mark_task_completed(fake_task))

    def test_parse_tasks_and_phases(self):
        content = (
            "# Implementation Plan\n\n"
            "### Phase 1: Setup\n"
            "- [x] Configure dependencies\n"
            "- [ ] Create initial test\n\n"
            "### Phase 2: Core\n"
            "- [ ] Implement service layer\n"
            "- [X] Setup logger\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "plan.md"
            plan_path.write_text(content, encoding="utf-8")

            mgr = PlanManager(plan_path)
            self.assertTrue(mgr.exists())
            self.assertEqual(mgr.read_content(), content)

            tasks = mgr.get_tasks()
            self.assertEqual(len(tasks), 4)

            self.assertEqual(tasks[0].index, 0)
            self.assertEqual(tasks[0].line_number, 4)
            self.assertEqual(tasks[0].phase, "Phase 1: Setup")
            self.assertEqual(tasks[0].description, "Configure dependencies")
            self.assertTrue(tasks[0].completed)

            self.assertEqual(tasks[1].index, 1)
            self.assertEqual(tasks[1].line_number, 5)
            self.assertEqual(tasks[1].phase, "Phase 1: Setup")
            self.assertEqual(tasks[1].description, "Create initial test")
            self.assertFalse(tasks[1].completed)

            self.assertEqual(tasks[2].index, 2)
            self.assertEqual(tasks[2].line_number, 8)
            self.assertEqual(tasks[2].phase, "Phase 2: Core")
            self.assertEqual(tasks[2].description, "Implement service layer")
            self.assertFalse(tasks[2].completed)

            self.assertEqual(tasks[3].index, 3)
            self.assertEqual(tasks[3].line_number, 9)
            self.assertEqual(tasks[3].phase, "Phase 2: Core")
            self.assertEqual(tasks[3].description, "Setup logger")
            self.assertTrue(tasks[3].completed)

            next_task = mgr.get_next_task()
            self.assertIsNotNone(next_task)
            assert next_task is not None
            self.assertEqual(next_task.index, 1)
            self.assertEqual(next_task.description, "Create initial test")

    def test_is_phase_boundary(self):
        mgr = PlanManager(Path("dummy.md"))
        t1 = PlanTask(index=0, line_number=1, phase="Phase 1", description="Task 1", completed=True)
        t2 = PlanTask(index=1, line_number=2, phase="Phase 1", description="Task 2", completed=False)
        t3 = PlanTask(index=2, line_number=3, phase="Phase 2", description="Task 3", completed=False)

        self.assertFalse(mgr.is_phase_boundary(None, t1))
        self.assertFalse(mgr.is_phase_boundary(t1, None))
        self.assertFalse(mgr.is_phase_boundary(t1, t2))
        self.assertTrue(mgr.is_phase_boundary(t2, t3))

    def test_mark_task_completed(self):
        content = (
            "### Phase 1\n"
            "- [ ] First step\n"
            "- [ ] Second step\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "plan.md"
            plan_path.write_text(content, encoding="utf-8")

            mgr = PlanManager(plan_path)
            task1 = mgr.get_next_task()
            self.assertIsNotNone(task1)
            assert task1 is not None
            self.assertEqual(task1.description, "First step")

            success = mgr.mark_task_completed(task1)
            self.assertTrue(success)

            updated_tasks = mgr.get_tasks()
            self.assertTrue(updated_tasks[0].completed)
            self.assertFalse(updated_tasks[1].completed)

            task2 = mgr.get_next_task()
            self.assertIsNotNone(task2)
            assert task2 is not None
            self.assertEqual(task2.description, "Second step")

            mgr.mark_task_completed(task2)
            self.assertIsNone(mgr.get_next_task())


if __name__ == "__main__":
    unittest.main()
