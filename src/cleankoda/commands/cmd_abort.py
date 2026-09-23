"""Slash-command handler for /abort discarding active plan review or pausing execution."""

from pathlib import Path

from cleankoda.commands.cmd_plan import sanitize_filename
from cleankoda.commands.command_registry import CommandContext, CommandResult, registry
from cleankoda.state import (
    AgentActivity,
    clear_status,
    get_activity,
    get_active_issue,
    set_activity,
)


@registry.register(
    "abort",
    description="Abort plan review or pause execution",
    usage="/abort",
)
async def cmd_abort(args: list[str], ctx: CommandContext) -> CommandResult:
    """Slash-command handler for /abort handling plan discard or execution pause."""
    clear_status("action_hint")
    activity = get_activity()

    if activity == AgentActivity.REVIEWING_PLAN:
        active_issue = get_active_issue()
        workspace_path = (
            ctx.agent.sandbox.workspace
            if (ctx.agent and getattr(ctx.agent, "sandbox", None))
            else Path.cwd()
        )
        plans_dir = workspace_path / ".cleankoda" / "plans"

        if plans_dir.exists():
            if active_issue:
                safe_title = sanitize_filename(active_issue.title)
                file_name = f"plan_{safe_title}_{active_issue.id}.md"
                plan_file = plans_dir / file_name
                if plan_file.exists():
                    plan_file.unlink()
            else:
                # Remove recent plan files if no active issue
                for plan_file in plans_dir.glob("plan_*.md"):
                    try:
                        plan_file.unlink()
                    except OSError:
                        pass

        set_activity(AgentActivity.IDLE)
        return CommandResult(output="Plan discarded.")

    elif activity == AgentActivity.REVIEWING_CODE:
        set_activity(AgentActivity.IDLE)
        return CommandResult(
            output="Execution paused. You can resume anytime with /execute."
        )

    else:
        set_activity(AgentActivity.IDLE)
        return CommandResult(output="Nothing to abort.")
