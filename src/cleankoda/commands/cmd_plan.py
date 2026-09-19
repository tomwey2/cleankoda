import re
from pathlib import Path
from typing import TYPE_CHECKING

from cleankoda.agent import Agent
from cleankoda.commands.command_registry import CommandContext, CommandResult, registry
from cleankoda.prompts import USER_PROMPT_PLAN
from cleankoda.state import ActiveIssueContext, get_active_issue
from cleankoda.tools.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from cleankoda.tui import TUI


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


async def create_plan_with_tui(
    tui: "TUI",
    agent: Agent,
    active_issue: ActiveIssueContext | None,
    goal_arg: str,
) -> list[str]:
  """Executes the agent in TUI mode, streams tool calls to the UI,

  and collects ONLY the final plan text (discarding intermediate reasoning
  before tools).
  """
  app = getattr(tui, "app", None)
  final_plan_chunks: list[str] = []
  current_turn_chunks: list[str] = []

  target_desc = (
      f"#{active_issue.id} ({active_issue.title})"
      if active_issue
      else f"'{goal_arg}'"
  )
  user_msg = (
      f"> /plan {goal_arg}\n\n  [Planer] Generating implementation plan for"
      f" {target_desc}...\n"
  )
  tui.history_area.text += f"\n\n{user_msg}"
  tui.history_area.buffer.cursor_position = len(tui.history_area.text)
  if app:
    app.invalidate()

  cancel_ev = getattr(tui, "cancel_event", None)

  async for chunk in agent.run(cancel_event=cancel_ev):
    if is_tool_call_display(chunk, agent.tool_registry):
      # Tool wird ausgeführt: Vorherige Ankündigungs-Texte verwerfen!
      current_turn_chunks.clear()

      tool_line = f"  ⚙ [Tool] {chunk.strip()}\n"
      tui.history_area.text += tool_line
      tui.history_area.buffer.cursor_position = len(tui.history_area.text)
      if app:
        app.invalidate()
    else:
      # Text sammeln, der nach/ohne Tools generiert wird
      current_turn_chunks.append(chunk)

  # Was nach allen Tool-Ausführungen übrig bleibt, ist der eigentliche Plan
  final_plan_chunks = current_turn_chunks
  return final_plan_chunks


async def create_plan_headless(agent: Agent) -> list[str]:
  """Executes the agent in headless mode and collects only the final plan output."""
  current_turn_chunks: list[str] = []

  async for chunk in agent.run():
    if is_tool_call_display(chunk, agent.tool_registry):
      current_turn_chunks.clear()
    else:
      current_turn_chunks.append(chunk)

  return current_turn_chunks


@registry.register(
    "plan",
    description=(
        "Create a step-by-step implementation plan incorporating active issue"
        " context"
    ),
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
            "Use '/issue' to select an active issue or provide a goal"
            " description: '/plan <goal>'."
        )
    )

  # DRY: Issue-Details NICHT wiederholen, da sie bereits im System-Prompt verankert sind.
  additional_focus = (
      f"\n### Specific Focus / Directive:\n{goal_arg}\n" if goal_arg else ""
  )

  prompt = USER_PROMPT_PLAN.format(additional_focus=additional_focus)
  ctx.memory.add_user(prompt)

  if ctx.agent:
    app = ctx.app
    tui = getattr(app, "tui", None) if app else None

    if tui:
      plan_chunks = await create_plan_with_tui(
          tui, ctx.agent, active_issue, goal_arg
      )
    else:
      plan_chunks = await create_plan_headless(ctx.agent)

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
          "\n  ✓ Implementation plan successfully generated and saved:\n"
          f"    → {rel_path}\n"
      )
      if tui:
        tui.history_area.text += success_msg
        tui.history_area.buffer.cursor_position = len(tui.history_area.text)
        app.invalidate()
      else:
        return CommandResult(output=f"{full_plan}\n\nSaved to {rel_path}")

      return CommandResult(output=None)
    else:
      err_msg = (
          "\n  ✗ Error: Agent completed work but returned an empty plan."
      )
      if tui:
        tui.history_area.text += err_msg
        tui.history_area.buffer.cursor_position = len(tui.history_area.text)
        app.invalidate()
      return CommandResult(output=err_msg)

  return CommandResult(output=prompt)
