import asyncio
import sys
import httpx
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Float, FloatContainer, HSplit
from prompt_toolkit.shortcuts import radiolist_dialog
from prompt_toolkit.widgets import Button, Dialog, Label, RadioList

from cleankoda.commands.command_registry import CommandContext, CommandResult, registry
from cleankoda.its.config import IssueState
from cleankoda.its.its import Issue
from cleankoda.its.trello_client import TrelloClient


def extract_trello_card_id(input_str: str) -> str:
    """Extract raw card ID or shortlink from a Trello URL or plain string."""
    clean_str = input_str.strip()
    if "trello.com/c/" in clean_str:
        part = clean_str.split("trello.com/c/")[1]
        card_id = part.split("/")[0].split("?")[0].split("#")[0]
        return card_id
    return clean_str.strip("/")


async def _show_tui_modal_issue_dialog(
    app: Application,
    float_container: FloatContainer,
    issues: list[Issue],
) -> str | None:
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[str | None] = loop.create_future()

    values = [(issue.id, issue.name) for issue in issues]
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
        title="Trello: Todo Cards",
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

    values = [(issue.id, issue.name) for issue in issues]
    dialog = radiolist_dialog(
        title="Trello: Todo Cards",
        text="Select a user story to create an implementation plan:",
        values=values,
        default=issues[0].id if issues else None,
    )
    return dialog.run()


@registry.register(
    "issue-to-plan",
    description="Create an implementation plan from a Trello Todo ticket",
    usage="/issue-to-plan [card_id_or_url]",
)
async def cmd_issue_to_plan(args: list[str], ctx: CommandContext) -> CommandResult:
    """Slash-command handler for /issue-to-plan."""
    try:
        trello = TrelloClient()
    except Exception as e:
        return CommandResult(output=f"Error initializing Trello client: {e}")

    if args:
        raw_arg = args[0].strip()
        card_id = extract_trello_card_id(raw_arg)
    else:
        try:
            todo_issues = await trello.get_issues_from_state(IssueState.TODO)
        except (httpx.HTTPError, RuntimeError, ValueError) as e:
            return CommandResult(output=f"Error fetching Todo cards: {e}")

        if not todo_issues:
            return CommandResult(output="No open cards found in the 'Todo' list.")

        selected_id = await select_issue_interactive(ctx, todo_issues)
        if selected_id is None:
            return CommandResult(output="Ticket selection cancelled.")
        card_id = selected_id

    try:
        issue = await trello.get_issue(card_id)
    except (httpx.HTTPError, RuntimeError, ValueError) as e:
        return CommandResult(output=f"Error fetching ticket '{card_id}': {e}")

    prompt = (
        "Create a detailed implementation plan for the following user story:\n\n"
        f"### Ticket: {issue.name}\n"
        f"### Description:\n"
        f"{issue.description}\n\n"
        "### Requirements for the plan:\n"
        "1. Architectural approach & affected modules/files.\n"
        "2. Step-by-step implementation order.\n"
        "3. Necessary unit tests & validation strategy."
    )

    ctx.memory.add_user(prompt)

    if ctx.agent:
        app = ctx.app
        tui = getattr(app, "tui", None) if app else None
        if tui:
            user_msg = f"> /issue-to-plan {card_id}\n\n  "
            tui.history_area.text += f"\n\n{user_msg}"
            tui.history_area.buffer.cursor_position = len(tui.history_area.text)
            app.invalidate()

            cancel_ev = getattr(tui, "cancel_event", None)
            async for chunk in ctx.agent.run(cancel_event=cancel_ev):
                indented_chunk = chunk.replace("\n", "\n  ")
                tui.history_area.text += indented_chunk
                tui.history_area.buffer.cursor_position = len(tui.history_area.text)
                app.invalidate()
        else:
            async for chunk in ctx.agent.run():
                print(chunk, end="", flush=True)
            print()

        return CommandResult(output=None)

    return CommandResult(output=prompt)
