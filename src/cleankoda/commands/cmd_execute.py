"""Slash-command handler for /execute running plan tasks step-by-step."""

from pathlib import Path

from cleankoda.commands.cmd_plan import is_tool_call_display, sanitize_filename
from cleankoda.commands.command_registry import CommandContext, CommandResult, registry
from cleankoda.plans.manager import PlanManager, PlanTask
from cleankoda.prompts import USER_PROMPT_EXECUTE
from cleankoda.state import get_active_issue


def should_pause_for_review(
    previous_task: PlanTask | None, next_task: PlanTask
) -> bool:
    """Hook function to determine if execution should pause for human-in-the-loop review.

    Default implementation returns False. Can be customized to pause at phase boundaries,
    critical markers, or specific task indexes.

    Args:
        previous_task: The task that was just executed (None if first task).
        next_task: The next task to be executed.

    Returns:
        True if execution should pause for review, False otherwise.
    """
    return False


@registry.register(
    "execute",
    description="Execute open tasks from the implementation plan step-by-step or all at once",
    usage="/execute [all]",
)
async def cmd_execute(args: list[str], ctx: CommandContext) -> CommandResult:
    """Slash-command handler for /execute running plan tasks iteratively."""
    active_issue = get_active_issue()
    if not active_issue:
        return CommandResult(
            output="No active issue set. Use '/issue' to select an active issue before running '/execute'."
        )

    workspace_path = (
        ctx.agent.sandbox.workspace
        if (ctx.agent and ctx.agent.sandbox)
        else Path.cwd()
    )
    plans_dir = workspace_path / ".cleankoda" / "plans"
    safe_title = sanitize_filename(active_issue.title)
    file_name = f"plan_{safe_title}_{active_issue.id}.md"
    plan_path = plans_dir / file_name

    plan_mgr = PlanManager(plan_path)
    if not plan_mgr.exists():
        rel_path = f".cleankoda/plans/{file_name}"
        return CommandResult(
            output=f"No implementation plan found at {rel_path}. Run '/plan' to generate one first."
        )

    run_all = bool(args and args[0].lower() in ("all", "--all"))

    app = ctx.app
    tui = getattr(app, "tui", None) if app else None

    previous_task: PlanTask | None = None
    tasks_executed = 0

    while True:
        tasks = plan_mgr.get_tasks()
        next_task = plan_mgr.get_next_task()

        if next_task is None:
            done_msg = "\n  ✓ All tasks in implementation plan have been completed!\n"
            if tui:
                tui.history_area.text += done_msg
                tui.history_area.buffer.cursor_position = len(tui.history_area.text)
                if app:
                    app.invalidate()
            return CommandResult(output="All tasks in implementation plan completed!")

        if should_pause_for_review(previous_task, next_task):
            pause_msg = (
                f"\n  ⏸ Execution paused for review before task [{next_task.index + 1}]: "
                f"{next_task.description}\n"
            )
            if tui:
                tui.history_area.text += pause_msg
                tui.history_area.buffer.cursor_position = len(tui.history_area.text)
                if app:
                    app.invalidate()
            return CommandResult(
                output=f"Paused for review before task {next_task.index + 1}: {next_task.description}"
            )

        total_tasks = len(tasks)
        task_header = f"▶ [{next_task.index + 1}/{total_tasks}] Executing: {next_task.description}"

        if tui:
            tui.history_area.text += f"\n\n  {task_header}\n"
            tui.history_area.buffer.cursor_position = len(tui.history_area.text)
            if app:
                app.invalidate()

        plan_content = plan_mgr.read_content()
        prompt = USER_PROMPT_EXECUTE.format(
            task_description=next_task.description,
            plan_content=plan_content,
        )
        ctx.memory.add_user(prompt)

        if ctx.agent:
            cancel_ev = getattr(tui, "cancel_event", None) if tui else None
            async for chunk in ctx.agent.run(cancel_event=cancel_ev):
                if tui:
                    if is_tool_call_display(chunk, ctx.agent.tool_registry):
                        tool_line = f"  ⚙ [Tool] {chunk.strip()}\n"
                        tui.history_area.text += tool_line
                    else:
                        indented_chunk = chunk.replace("\n", "\n  ")
                        tui.history_area.text += indented_chunk
                    tui.history_area.buffer.cursor_position = len(tui.history_area.text)
                    if app:
                        app.invalidate()

        plan_mgr.mark_task_completed(next_task)
        tasks_executed += 1

        completed_msg = (
            f"\n  ✓ Task completed & marked done in plan: {next_task.description}\n"
        )
        if tui:
            tui.history_area.text += completed_msg
            tui.history_area.buffer.cursor_position = len(tui.history_area.text)
            if app:
                app.invalidate()

        previous_task = next_task
        remaining_task = plan_mgr.get_next_task()

        if not remaining_task:
            finish_msg = "\n  ✓ All tasks in implementation plan have been completed!\n"
            if tui:
                tui.history_area.text += finish_msg
                tui.history_area.buffer.cursor_position = len(tui.history_area.text)
                if app:
                    app.invalidate()
            return CommandResult(output="All tasks in implementation plan completed!")

        if not run_all or should_pause_for_review(previous_task, remaining_task):
            info_msg = (
                f"\n  ℹ Task [{next_task.index + 1}/{total_tasks}] finished.\n"
                f"    Next open task [{remaining_task.index + 1}/{total_tasks}]: {remaining_task.description}\n"
                "    Run '/execute' or '/execute all' to continue.\n"
            )
            if tui:
                tui.history_area.text += info_msg
                tui.history_area.buffer.cursor_position = len(tui.history_area.text)
                if app:
                    app.invalidate()
            return CommandResult(
                output=f"Task {next_task.index + 1} completed. Next open task [{remaining_task.index + 1}/{total_tasks}]: {remaining_task.description}"
            )
