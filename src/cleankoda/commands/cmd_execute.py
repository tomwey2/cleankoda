"""Slash-command handler for /execute running plan tasks step-by-step with HITL review checkpoints."""

from pathlib import Path
import re
from typing import Any

from cleankoda.commands.cmd_plan import is_tool_call_display, sanitize_filename
from cleankoda.commands.command_registry import CommandContext, CommandResult, registry
from cleankoda.plans.manager import PlanManager, PlanTask
from cleankoda.prompts import USER_PROMPT_EXECUTE
from cleankoda.state import (
    AgentActivity,
    get_activity,
    get_active_issue,
    set_activity,
    set_error_state,
)

REVIEW_PHASE_KEYWORDS = re.compile(
    r"(?i)red phase|green phase|service|controller|test|implementation|config|setup"
)


async def get_workspace_diff(agent: Any | None) -> str:
    """Fetch compact git status and diff output from the project workspace.

    Args:
        agent: Agent instance with sandbox environment access.

    Returns:
        Formatted git status and diff text, truncated to max 1,500 chars.
    """
    if not agent or not getattr(agent, "sandbox", None) or not getattr(agent.sandbox, "current_env", None):
        return "(No sandbox environment available for diff)"

    env = agent.sandbox.current_env
    status_res = await env.run(command="git status -s", timeout=10)
    diff_res = await env.run(command="git diff", timeout=15)

    status_out = status_res.get("output", "").strip() or status_res.get("stdout", "").strip()
    diff_out = diff_res.get("output", "").strip() or diff_res.get("stdout", "").strip()

    status_str = f"--- Git Status ---\n{status_out}\n" if status_out else "--- Git Status ---\n(Clean working tree)\n"
    diff_str = f"--- Git Diff ---\n{diff_out}\n" if diff_out else ""

    combined = f"{status_str}{diff_str}".strip()
    if len(combined) > 1500:
        combined = combined[:1450] + "\n[... diff truncated at 1,500 chars ...]"

    return combined


def should_request_review(
    previous_task: PlanTask | None, next_task: PlanTask | None
) -> bool:
    """Determine if execution should request a human-in-the-loop review.

    Triggers at phase boundaries when the completed phase matches key milestone keywords.

    Args:
        previous_task: The task that was executed previously (or None).
        next_task: The next task to be executed (or None).

    Returns:
        True if execution should pause for review, False otherwise.
    """
    if previous_task is None or next_task is None:
        return False
    if previous_task.phase == next_task.phase:
        return False

    return bool(REVIEW_PHASE_KEYWORDS.search(previous_task.phase)) or True


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
    is_paused_for_review = False

    try:
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
                set_activity(AgentActivity.IDLE)
                return CommandResult(output="All tasks in implementation plan completed!")

            total_tasks = len(tasks)

            # Check HITL Review Checkpoint at phase boundary
            if previous_task is not None and should_request_review(previous_task, next_task):
                is_paused_for_review = True
                milestone_phase = previous_task.phase
                milestone_banner = f"\n  ⏸ PHASE COMPLETED: {milestone_phase}\n"
                diff_summary = await get_workspace_diff(ctx.agent)
                indented_diff = "\n".join(f"    {line}" for line in diff_summary.splitlines())

                review_msg = (
                    f"{milestone_banner}\n{indented_diff}\n\n"
                    f"  ℹ Execution paused for review at milestone '{milestone_phase}'.\n"
                    f"    Next open task [{next_task.index + 1}/{total_tasks}]: {next_task.description}\n"
                    "    Resume anytime with /execute or /execute all.\n"
                )

                if tui:
                    tui.history_area.text += review_msg
                    tui.history_area.buffer.cursor_position = len(tui.history_area.text)
                    if app:
                        app.invalidate()

                set_activity(AgentActivity.REVIEWING, f"Reviewing changes after: {previous_task.description}")
                return CommandResult(
                    output=(
                        f"Execution paused for review at milestone '{milestone_phase}'. "
                        f"Next open task [{next_task.index + 1}/{total_tasks}]: {next_task.description}"
                    )
                )

            set_activity(AgentActivity.CODING, next_task.description)
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
                set_activity(AgentActivity.IDLE)
                return CommandResult(output="All tasks in implementation plan completed!")

            if not run_all:
                is_paused_for_review = True
                set_activity(AgentActivity.REVIEWING, f"Review step: {next_task.description}")
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
    except Exception as e:
        set_error_state(str(e))
        raise
    finally:
        if not is_paused_for_review and get_activity() not in (AgentActivity.REVIEWING, AgentActivity.ERROR):
            set_activity(AgentActivity.IDLE)
