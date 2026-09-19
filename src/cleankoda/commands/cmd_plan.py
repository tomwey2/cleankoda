import re
from pathlib import Path

from cleankoda.commands.command_registry import CommandContext, CommandResult, registry
from cleankoda.state import get_active_issue
from cleankoda.tools.tool_registry import ToolRegistry


def sanitize_filename(text: str) -> str:
    """Sanitizes text for safe use as a filename component."""
    text = text.lower().strip()
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"[^a-z0-9\-]", "", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    return text or "plan"


def is_tool_call_display(chunk: str, registry_inst: ToolRegistry) -> bool:
    """Determines whether a chunk string emitted during agent execution represents a tool call."""
    stripped = chunk.strip()
    if "(" in stripped and stripped.endswith(")"):
        func_name = stripped.split("(", 1)[0].strip()
        schemas = registry_inst.get_schemas()
        registered_names = {
            s.get("function", {}).get("name") if s.get("type") == "function" else s.get("name")
            for s in schemas
        }
        if func_name in registered_names:
            return True
    return False


@registry.register(
    "plan",
    description="Create a step-by-step implementation plan incorporating active issue context",
    usage="/plan [goal]",
)
async def cmd_plan(args: list[str], ctx: CommandContext) -> CommandResult:
    """Slash-command handler for /plan generating an implementation plan saved to disk."""
    active_issue = get_active_issue()
    goal_arg = " ".join(args).strip() if args else ""

    if not active_issue and not goal_arg:
        return CommandResult(
            output=(
                "No active issue set and no goal specified. "
                "Use '/issue' to select an active issue or provide a goal description: '/plan <goal>'."
            )
        )

    prompt_parts = [
        "Inspect the local workspace using your tools (e.g., list_dir, read_file) "
        "to gather necessary context, then create a detailed implementation plan."
    ]

    if active_issue:
        prompt_parts.append(
            f"Active Ticket: #{active_issue.id} - {active_issue.title}\n"
            f"Status: {active_issue.status}\n"
            f"Description:\n{active_issue.description or 'No description available.'}"
        )

    if goal_arg:
        prompt_parts.append(f"Additional Directive / Goal: {goal_arg}")

    prompt_parts.append(
        "Requirements for the plan:\n"
        "1. Architectural approach & affected modules/files.\n"
        "2. Step-by-step implementation order.\n"
        "3. Necessary unit tests & validation strategy."
    )

    prompt = "\n\n".join(prompt_parts)
    ctx.memory.add_user(prompt)

    if ctx.agent:
        app = ctx.app
        tui = getattr(app, "tui", None) if app else None

        plan_chunks: list[str] = []

        if tui:
            target_desc = f"#{active_issue.id} ({active_issue.title})" if active_issue else f"'{goal_arg}'"
            user_msg = f"> /plan {goal_arg}\n\n  [Planer] Generating implementation plan for {target_desc}...\n"
            tui.history_area.text += f"\n\n{user_msg}"
            tui.history_area.buffer.cursor_position = len(tui.history_area.text)
            app.invalidate()

            cancel_ev = getattr(tui, "cancel_event", None)
            async for chunk in ctx.agent.run(cancel_event=cancel_ev):
                if is_tool_call_display(chunk, ctx.agent.tool_registry):
                    tool_line = f"  [Tool] {chunk.strip()}\n"
                    tui.history_area.text += tool_line
                    tui.history_area.buffer.cursor_position = len(tui.history_area.text)
                    app.invalidate()
                else:
                    plan_chunks.append(chunk)
        else:
            async for chunk in ctx.agent.run():
                if is_tool_call_display(chunk, ctx.agent.tool_registry):
                    pass
                else:
                    plan_chunks.append(chunk)

        full_plan = "".join(plan_chunks).strip()

        if full_plan:
            workspace_path = (
                ctx.agent.sandbox.workspace
                if (ctx.agent and ctx.agent.sandbox)
                else Path.cwd()
            )
            plans_dir = workspace_path / ".cleankoda" / "plans"
            plans_dir.mkdir(parents=True, exist_ok=True)

            if active_issue:
                safe_title = sanitize_filename(active_issue.title)
                file_name = f"plan_{safe_title}_{active_issue.id}.md"
            else:
                safe_title = sanitize_filename(goal_arg[:30])
                file_name = f"plan_{safe_title}.md"

            target_file = plans_dir / file_name
            target_file.write_text(full_plan, encoding="utf-8")

            rel_path = f".cleankoda/plans/{file_name}"
            success_msg = (
                f"\n  ✓ Implementation plan successfully generated and saved:\n"
                f"    → {rel_path}\n"
            )
            if tui:
                tui.history_area.text += success_msg
                tui.history_area.buffer.cursor_position = len(tui.history_area.text)
                app.invalidate()
            else:
                return CommandResult(output=f"{full_plan}\n\nSaved to {rel_path}")

        return CommandResult(output=None)

    return CommandResult(output=prompt)
