import asyncio
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Float, FloatContainer, HSplit
from prompt_toolkit.shortcuts import radiolist_dialog
from prompt_toolkit.widgets import Button, Dialog, Label, RadioList

from cleankoda.commands.command_registry import CommandContext, CommandResult, registry
from cleankoda.its.config import IssueState
from cleankoda.its.its import Issue
from cleankoda.state import (
    ActiveIssueContext,
    clear_active_issue,
    get_active_issue,
    set_active_issue,
)
from cleankoda.tools.mcp_client import connect_mcp_server


def extract_trello_card_id(input_str: str) -> str:
    """Extract raw card ID or shortlink from a Trello URL or plain string."""
    clean_str = input_str.strip()
    if "trello.com/c/" in clean_str:
        part = clean_str.split("trello.com/c/")[1]
        card_id = part.split("/")[0].split("?")[0].split("#")[0]
        return card_id
    return clean_str.strip("/")


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
        title="Todo Issues",
        body=HSplit([
            Label("Select an issue to focus:"),
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
        tui = getattr(app, "tui", None)
        if tui and hasattr(tui, "input_field"):
            tui.input_field.text = ""
            tui.input_field.buffer.cursor_position = 0
            try:
                app.layout.focus(tui.input_field)
            except Exception:
                pass
        elif original_focused:
            try:
                app.layout.focus(original_focused)
            except Exception:
                pass
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
        title="Todo Issues",
        text="Select an issue to focus:",
        values=values,
        default=issues[0].id if issues else None,
    )
    return await dialog.run_async()


async def _fetch_and_set_issue(
    session: Any, issue_id: str, ctx: CommandContext | None = None
) -> CommandResult:
    """Helper to fetch details via MCP session and update global active_issue."""
    try:
        async with asyncio.timeout(10.0):
            res_details = await session.call_tool(
                "get_issue_details", arguments={"issue_id": issue_id}
            )
        text_blocks = []
        if res_details and res_details.content:
            text_blocks = [
                item.text for item in res_details.content if hasattr(item, "text")
            ]
        details_json = "\n".join(text_blocks)
        details_dict = json.loads(details_json) if details_json else {}

        active = ActiveIssueContext(
            id=details_dict.get("id", issue_id),
            title=details_dict.get("title", f"Issue {issue_id}"),
            description=details_dict.get("description", ""),
            state=IssueState.TODO,
            state_id=details_dict.get("state_id", ""),
            state_name=details_dict.get("state_name", ""),
            url=details_dict.get("url"),
        )
        set_active_issue(active)
        if ctx and ctx.app:
            tui = getattr(ctx.app, "tui", None)
            if tui and hasattr(tui, "on_status_changed"):
                tui.on_status_changed()
            ctx.app.invalidate()

        return CommandResult(
            output=f"Active issue set: #{active.id} - {active.title}"
        )
    except (TimeoutError, asyncio.TimeoutError):
        return CommandResult(
            output=f"Error fetching ticket details for '{issue_id}': Request timed out after 10.0 seconds."
        )
    except Exception as e:
        return CommandResult(
            output=f"Error fetching ticket details for '{issue_id}': {e}"
        )


@registry.register(
    "issue",
    description="Manage stateful active issue context via MCP",
    usage="/issue [show|clear|sync|<id_or_url>]",
)
async def cmd_issue(args: list[str], ctx: CommandContext) -> CommandResult:
    """Slash-command handler for stateful /issue operations."""
    subcommand = args[0].strip() if args else ""

    if subcommand == "show":
        active = get_active_issue()
        if not active:
            return CommandResult(output="No active issue currently set.")
        url_str = active.url or "N/A"
        desc_str = active.description.strip() or "No description available."
        output = (
            f"[Active Issue]: #{active.id} - {active.title}\n"
            f"State: {active.state}\n"
            f"URL: {url_str}\n\n"
            f"Description:\n{desc_str}"
        )
        return CommandResult(output=output)

    if subcommand == "clear":
        clear_active_issue()
        if ctx and ctx.app:
            tui = getattr(ctx.app, "tui", None)
            if tui and hasattr(tui, "on_status_changed"):
                tui.on_status_changed()
            ctx.app.invalidate()
        return CommandResult(output="Active issue cleared.")

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
        if subcommand == "sync":
            active = get_active_issue()
            if not active:
                return CommandResult(output="No active issue to sync.")
            return await _fetch_and_set_issue(session, active.id, ctx=ctx)

        if subcommand:
            card_id = extract_trello_card_id(subcommand)
            return await _fetch_and_set_issue(session, card_id, ctx=ctx)

        # No args: fetch Todo list via get_issues
        try:
            async with asyncio.timeout(10.0):
                res_issues = await session.call_tool(
                    "get_issues", arguments={"state": IssueState.TODO}
                )
            text_content = ""
            if res_issues and res_issues.content:
                text_blocks = [
                    item.text for item in res_issues.content if hasattr(item, "text")
                ]
                text_content = "\n".join(text_blocks)

            todo_issues = parse_mcp_issues_response(text_content)
        except (TimeoutError, asyncio.TimeoutError):
            return CommandResult(
                output="Error fetching Todo cards via MCP: Request timed out after 10.0 seconds."
            )
        except Exception as e:
            return CommandResult(output=f"Error fetching Todo cards via MCP: {e}")

        if not todo_issues:
            return CommandResult(output="No open cards found in the 'Todo' list.")

        selected_id = await select_issue_interactive(ctx, todo_issues)
        if selected_id is None:
            return CommandResult(output="Issue selection cancelled.")

        return await _fetch_and_set_issue(session, selected_id, ctx=ctx)

    finally:
        try:
            async with asyncio.timeout(2.0):
                await exit_stack.aclose()
        except Exception:
            pass
