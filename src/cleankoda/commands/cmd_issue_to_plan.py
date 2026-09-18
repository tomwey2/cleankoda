import asyncio
import json
import os
from pathlib import Path
import re
import sys

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Float, FloatContainer, HSplit
from prompt_toolkit.shortcuts import radiolist_dialog
from prompt_toolkit.widgets import Button, Dialog, Label, RadioList

from cleankoda.commands.command_registry import CommandContext, CommandResult, registry
from cleankoda.its.its import Issue, IssueState
from cleankoda.tools.mcp_client import connect_mcp_server
from cleankoda.tools.tool_registry import ToolRegistry


def extract_trello_card_id(input_str: str) -> str:
    """Extract raw card ID or shortlink from a Trello URL or plain string."""
    clean_str = input_str.strip()
    if "trello.com/c/" in clean_str:
        part = clean_str.split("trello.com/c/")[1]
        card_id = part.split("/")[0].split("?")[0].split("#")[0]
        return card_id
    return clean_str.strip("/")


def sanitize_filename(text: str) -> str:
    """Sanitizes text for safe use as a filename component."""
    text = text.lower().strip()
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"[^a-z0-9\-]", "", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    return text or "ticket"


def parse_mcp_issues_response(raw_text: str) -> list[Issue]:
    """Parses text output from get_issues MCP tool into a list of Issue domain models."""
    issues: list[Issue] = []
    lines = raw_text.strip().split("\n")
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        match = re.match(r"^-\s*\[([^\]]+)\]\s*([^:]+):", line_str)
        if match:
            issue_id = match.group(1).strip()
            title = match.group(2).strip()
            issues.append(
                Issue(
                    id=issue_id,
                    title=title,
                    description="",
                    state_id="todo",
                    state_name="Todo",
                )
            )
    return issues


def is_tool_call_display(chunk: str, registry: ToolRegistry) -> bool:
    """Determines whether a chunk string emitted during agent execution represents a tool call."""
    stripped = chunk.strip()
    if "(" in stripped and stripped.endswith(")"):
        func_name = stripped.split("(", 1)[0].strip()
        schemas = registry.get_schemas()
        registered_names = {
            s.get("function", {}).get("name") if s.get("type") == "function" else s.get("name")
            for s in schemas
        }
        if func_name in registered_names:
            return True
    return False


async def _show_tui_modal_issue_dialog(
    app: Application,
    float_container: FloatContainer,
    issues: list[Issue],
) -> str | None:
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[str | None] = loop.create_future()

    values = [(issue.id, issue.title) for issue in issues]
    radio_list = RadioList(values=values, default=issues[0].id if issues else None)

    def on_ok() -> None:
        if not fut.done():
            fut.set_result(radio_list.current_value)

    def on_cancel() -> None:
        if not fut.done():
            fut.set_result(None)

    modal_kb = KeyBindings()

    @modal_kb.add("escape", eager=True)
    def _cancel(event):
        on_cancel()

    @modal_kb.add("enter")
    def _select(event):
        on_ok()

    dialog = Dialog(
        title="Todo Cards",
        body=HSplit([
            Label("Select a user story to create an implementation plan:"),
            radio_list,
        ]),
        buttons=[
            Button("OK", handler=on_ok),
            Button("Cancel", handler=on_cancel),
        ],
        width=65,
        with_background=True,
    )

    dialog_container = HSplit([dialog], key_bindings=modal_kb)
    dialog_float = Float(content=dialog_container)

    float_container.floats.append(dialog_float)
    original_focused = app.layout.current_window
    app.layout.focus(radio_list)
    app.invalidate()

    try:
        result = await fut
    finally:
        if dialog_float in float_container.floats:
            float_container.floats.remove(dialog_float)
        if original_focused:
            app.layout.focus(original_focused)
        app.invalidate()

    return result


async def select_issue_interactive(
    ctx: CommandContext | None,
    issues: list[Issue],
) -> str | None:
    """Interactive selection list for Todo cards (TUI modal or radiolist_dialog fallback)."""
    app = ctx.app if ctx else None
    float_container = getattr(app, "float_container", None) if app else None

    if app and float_container:
        return await _show_tui_modal_issue_dialog(app, float_container, issues)

    values = [(issue.id, issue.title) for issue in issues]
    dialog = radiolist_dialog(
        title="Todo Cards",
        text="Select a user story to create an implementation plan:",
        values=values,
        default=issues[0].id if issues else None,
    )
    return dialog.run()


@registry.register(
    "issue-to-plan",
    description="Create an implementation plan from an issue tracker card via MCP",
    usage="/issue-to-plan [card_id_or_url]",
)
async def cmd_issue_to_plan(args: list[str], ctx: CommandContext) -> CommandResult:
    """Slash-command handler for /issue-to-plan using MCP session and file persistence."""
    server_path = str(
        Path(__file__).parent.parent / "tools" / "mcp" / "issue_mcp_server.py"
    )
    if not os.path.exists(server_path):
        return CommandResult(output=f"Error: MCP server script not found at {server_path}")

    try:
        exit_stack, session = await connect_mcp_server(
            command=sys.executable,
            args=[server_path],
        )
    except Exception as e:
        return CommandResult(output=f"Error connecting to MCP issue server: {e}")

    try:
        if ctx.agent and hasattr(ctx.agent, "tool_registry"):
            await ctx.agent.tool_registry.register_mcp_session(session)

        card_id: str = ""
        title: str = ""
        description: str = ""

        if args:
            raw_arg = args[0].strip()
            card_id = extract_trello_card_id(raw_arg)
        else:
            try:
                res_issues = await session.call_tool("get_issues", arguments={"state": IssueState.TODO})
                text_content = ""
                if res_issues and res_issues.content:
                    text_blocks = [
                        item.text for item in res_issues.content if hasattr(item, "text")
                    ]
                    text_content = "\n".join(text_blocks)

                todo_issues = parse_mcp_issues_response(text_content)
            except Exception as e:
                return CommandResult(output=f"Error fetching Todo cards via MCP: {e}")

            if not todo_issues:
                return CommandResult(output="No open cards found in the 'Todo' list.")

            selected_id = await select_issue_interactive(ctx, todo_issues)
            if selected_id is None:
                return CommandResult(output="Ticket selection cancelled.")
            card_id = selected_id

        try:
            res_details = await session.call_tool("get_issue_details", arguments={"issue_id": card_id})
            text_blocks = []
            if res_details and res_details.content:
                text_blocks = [
                    item.text for item in res_details.content if hasattr(item, "text")
                ]
            details_json = "\n".join(text_blocks)
            details_dict = json.loads(details_json) if details_json else {}

            title = details_dict.get("title", f"Ticket {card_id}")
            description = details_dict.get("description", "")
        except Exception as e:
            return CommandResult(output=f"Error fetching ticket details for '{card_id}': {e}")

        prompt = (
            f"Create a detailed implementation plan for the following user story:\n\n"
            f"### Ticket: {title} (ID: {card_id})\n"
            f"### Description:\n"
            f"{description}\n\n"
            f"### Requirements for the plan:\n"
            f"1. Architectural approach & affected modules/files.\n"
            f"2. Step-by-step implementation order.\n"
            f"3. Necessary unit tests & validation strategy."
        )

        ctx.memory.add_user(prompt)

        if ctx.agent:
            app = ctx.app
            tui = getattr(app, "tui", None) if app else None

            plan_chunks: list[str] = []

            if tui:
                user_msg = f"> /issue-to-plan {card_id}\n\n  [Planer] Lade Kontext für Ticket #{card_id} ({title})...\n"
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
                print(f"  [Planer] Lade Kontext für Ticket #{card_id} ({title})...")
                async for chunk in ctx.agent.run():
                    if is_tool_call_display(chunk, ctx.agent.tool_registry):
                        print(f"  [Tool] {chunk.strip()}")
                    else:
                        plan_chunks.append(chunk)

            full_plan = "".join(plan_chunks).strip()

            if full_plan:
                safe_title = sanitize_filename(title)
                workspace_path = (
                    ctx.agent.sandbox.workspace
                    if (ctx.agent and ctx.agent.sandbox)
                    else Path.cwd()
                )
                plans_dir = workspace_path / ".cleankoda" / "plans"
                plans_dir.mkdir(parents=True, exist_ok=True)

                file_name = f"plan_{safe_title}_{card_id}.md"
                target_file = plans_dir / file_name
                target_file.write_text(full_plan, encoding="utf-8")

                rel_path = f".cleankoda/plans/{file_name}"
                success_msg = (
                    f"\n  ✓ Plan erfolgreich erstellt und gespeichert:\n"
                    f"    → {rel_path}\n"
                )
                if tui:
                    tui.history_area.text += success_msg
                    tui.history_area.buffer.cursor_position = len(tui.history_area.text)
                    app.invalidate()
                else:
                    print(success_msg)

            return CommandResult(output=None)

        return CommandResult(output=prompt)

    finally:
        await exit_stack.aclose()
