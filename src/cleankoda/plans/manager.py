"""Implementation plan management module for cleankoda.

Provides data structures and file manager for parsing and updating Markdown implementation plans.
"""

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class PlanTask:
    """Represents a single checkbox task in an implementation plan."""

    index: int
    line_number: int
    phase: str
    description: str
    completed: bool


class PlanManager:
    """Manager for reading, parsing, and updating Markdown implementation plans on disk."""

    def __init__(self, plan_path: Path) -> None:
        """Initialize PlanManager.

        Args:
            plan_path: Path to the target implementation plan Markdown file.
        """
        self.plan_path: Path = plan_path

    def exists(self) -> bool:
        """Check if the plan file exists."""
        return self.plan_path.exists()

    def read_content(self) -> str:
        """Read the full content of the plan file.

        Returns:
            The file content as string, or empty string if file does not exist.
        """
        if not self.exists():
            return ""
        return self.plan_path.read_text(encoding="utf-8")

    def get_tasks(self) -> list[PlanTask]:
        """Parse tasks from the plan Markdown file.

        Tracks phase headers starting with '###' and checkbox tasks '- [ ]' or '- [x]'.

        Returns:
            List of parsed PlanTask objects.
        """
        content = self.read_content()
        if not content:
            return []

        tasks: list[PlanTask] = []
        current_phase = "General"
        task_regex = re.compile(r"^(\s*-\s*\[)([ xX])(\]\s*)(.*)$")
        phase_regex = re.compile(r"^###\s+(.*)$")

        lines = content.splitlines()
        task_index = 0

        for line_idx, line in enumerate(lines, start=1):
            phase_match = phase_regex.match(line)
            if phase_match:
                current_phase = phase_match.group(1).strip()
                continue

            task_match = task_regex.match(line)
            if task_match:
                mark = task_match.group(2)
                completed = mark in ("x", "X")
                description = task_match.group(4).strip()
                tasks.append(
                    PlanTask(
                        index=task_index,
                        line_number=line_idx,
                        phase=current_phase,
                        description=description,
                        completed=completed,
                    )
                )
                task_index += 1

        return tasks

    def get_next_task(self) -> PlanTask | None:
        """Get the first uncompleted task in the plan.

        Returns:
            The first open PlanTask, or None if all tasks are completed or no tasks exist.
        """
        tasks = self.get_tasks()
        for task in tasks:
            if not task.completed:
                return task
        return None

    def mark_task_completed(self, task: PlanTask) -> bool:
        """Atomically mark a task as completed in the Markdown file.

        Replaces '- [ ]' with '- [x]' at the line corresponding to the task.

        Args:
            task: The PlanTask to mark as completed.

        Returns:
            True if the file was updated successfully, False otherwise.
        """
        if not self.exists():
            return False

        content = self.plan_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)

        if task.line_number < 1 or task.line_number > len(lines):
            return False

        target_line = lines[task.line_number - 1]
        new_line = re.sub(r"^(\s*-\s*\[)[ ](\])", r"\1x\2", target_line, count=1)
        lines[task.line_number - 1] = new_line
        new_content = "".join(lines)

        # Atomic write via temp file swap
        temp_file = self.plan_path.with_suffix(".tmp")
        temp_file.write_text(new_content, encoding="utf-8")
        temp_file.replace(self.plan_path)
        return True
