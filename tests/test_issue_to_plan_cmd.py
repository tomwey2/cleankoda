import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import CallToolResult, TextContent

from cleankoda.commands import CommandContext
from cleankoda.commands.cmd_issue_to_plan import (
    cmd_issue_to_plan,
    extract_trello_card_id,
    is_tool_call_display,
    parse_mcp_issues_response,
    sanitize_filename,
)
from cleankoda.tools import ToolRegistry


def test_extract_trello_card_id():
    assert extract_trello_card_id("AbCd1234") == "AbCd1234"
    assert extract_trello_card_id("AbCd1234/") == "AbCd1234"
    assert (
        extract_trello_card_id("https://trello.com/c/AbCd1234/123-user-story-title")
        == "AbCd1234"
    )
    assert (
        extract_trello_card_id("http://trello.com/c/AbCd1234?param=1#fragment")
        == "AbCd1234"
    )


def test_sanitize_filename():
    assert sanitize_filename("Improve README") == "improve-readme"
    assert (
        sanitize_filename("Stripe Webhook Handling! (v2.0)")
        == "stripe-webhook-handling-v20"
    )
    assert sanitize_filename("   ---Special   Chars***   ") == "special-chars"
    assert sanitize_filename("!!!") == "ticket"


def test_parse_mcp_issues_response():
    raw_output = (
        "- [card123] Add Feature X: Description of feature x...\n"
        "- [card456] Fix Bug Y: Description of bug y..."
    )
    issues = parse_mcp_issues_response(raw_output)
    assert len(issues) == 2
    assert issues[0].id == "card123"
    assert issues[0].title == "Add Feature X"
    assert issues[1].id == "card456"
    assert issues[1].title == "Fix Bug Y"


def test_is_tool_call_display():
    registry = MagicMock(spec=ToolRegistry)
    registry.get_schemas.return_value = [
        {"type": "function", "function": {"name": "read_file"}},
        {"type": "function", "function": {"name": "get_issue_details"}},
    ]
    assert is_tool_call_display("read_file(src/main.py)\n", registry) is True
    assert is_tool_call_display("get_issue_details(card123)\n", registry) is True
    assert (
        is_tool_call_display(
            "# Implementation Plan\nHere is step 1...", registry
        )
        is False
    )


@pytest.mark.anyio
async def test_cmd_issue_to_plan_with_card_id_arg():
    mock_memory = MagicMock()
    mock_agent = MagicMock()
    mock_agent.sandbox.workspace = Path(tempfile.mkdtemp())
    mock_agent.tool_registry = MagicMock(spec=ToolRegistry)
    mock_agent.tool_registry.get_schemas.return_value = []

    async def _mock_run(cancel_event=None):
        yield "# Plan for Feature X\n1. Step one..."

    mock_agent.run = _mock_run

    mock_app = MagicMock()
    mock_tui = MagicMock()
    mock_tui.history_area.text = ""
    mock_tui.history_area.buffer.cursor_position = 0
    mock_app.tui = mock_tui

    ctx = CommandContext(memory=mock_memory, agent=mock_agent, app=mock_app)

    mock_exit_stack = AsyncMock()
    mock_session = AsyncMock()

    details_dict = {
        "id": "card123",
        "title": "Add Feature X",
        "description": "Feature X description",
    }
    mock_session.call_tool.return_value = CallToolResult(
        content=[TextContent(type="text", text=json.dumps(details_dict))],
        isError=False,
    )

    with patch(
        "cleankoda.commands.cmd_issue_to_plan.connect_mcp_server",
        new_callable=AsyncMock,
        return_value=(mock_exit_stack, mock_session),
    ):
        res = await cmd_issue_to_plan(["card123"], ctx)

        mock_session.call_tool.assert_called_once_with(
            "get_issue_details", arguments={"issue_id": "card123"}
        )
        mock_memory.add_user.assert_called_once()
        assert res.output is None

        # Verify plan file persistence
        plan_file = (
            mock_agent.sandbox.workspace
            / ".cleankoda"
            / "plans"
            / "plan_add-feature-x_card123.md"
        )
        assert plan_file.is_file()
        assert "# Plan for Feature X" in plan_file.read_text(encoding="utf-8")

        # Verify TUI history area status streaming (no plan body text in history area)
        history = mock_tui.history_area.text
        assert "[Planer] Lade Kontext für Ticket #card123" in history
        assert "✓ Plan erfolgreich erstellt und gespeichert" in history
        assert "# Plan for Feature X" not in history


@pytest.mark.anyio
async def test_cmd_issue_to_plan_interactive_selection():
    mock_memory = MagicMock()
    mock_agent = MagicMock()
    mock_agent.sandbox.workspace = Path(tempfile.mkdtemp())
    mock_agent.tool_registry = MagicMock(spec=ToolRegistry)
    mock_agent.tool_registry.get_schemas.return_value = [
        {"type": "function", "function": {"name": "read_file"}}
    ]

    async def _mock_run(cancel_event=None):
        yield "read_file(src/api.py)\n"
        yield "Step 1: Refactor API endpoint..."

    mock_agent.run = _mock_run

    mock_app = MagicMock()
    mock_tui = MagicMock()
    mock_tui.history_area.text = ""
    mock_app.tui = mock_tui

    ctx = CommandContext(memory=mock_memory, agent=mock_agent, app=mock_app)

    mock_exit_stack = AsyncMock()
    mock_session = AsyncMock()

    mcp_issues_text = "- [c2] Story 2: Description 2..."
    details_dict = {
        "id": "c2",
        "title": "Story 2",
        "description": "Desc 2",
    }

    async def _mock_call_tool(name, arguments):
        if name == "get_issues":
            return CallToolResult(
                content=[TextContent(type="text", text=mcp_issues_text)],
                isError=False,
            )
        elif name == "get_issue_details":
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(details_dict))],
                isError=False,
            )

    mock_session.call_tool = AsyncMock(side_effect=_mock_call_tool)

    with (
        patch(
            "cleankoda.commands.cmd_issue_to_plan.connect_mcp_server",
            new_callable=AsyncMock,
            return_value=(mock_exit_stack, mock_session),
        ),
        patch(
            "cleankoda.commands.cmd_issue_to_plan.select_issue_interactive",
            new_callable=AsyncMock,
            return_value="c2",
        ),
    ):
        res = await cmd_issue_to_plan([], ctx)
        assert res.output is None

        # Verify tool call was logged in TUI history area
        history = mock_tui.history_area.text
        assert "[Tool] read_file(src/api.py)" in history
        assert "Step 1: Refactor API endpoint..." not in history

        # Verify file persisted
        plan_file = (
            mock_agent.sandbox.workspace / ".cleankoda" / "plans" / "plan_story-2_c2.md"
        )
        assert plan_file.is_file()
        assert "Step 1: Refactor API endpoint..." in plan_file.read_text(encoding="utf-8")


@pytest.mark.anyio
async def test_cmd_issue_to_plan_empty_todo_list():
    mock_memory = MagicMock()
    ctx = CommandContext(memory=mock_memory)

    mock_exit_stack = AsyncMock()
    mock_session = AsyncMock()
    mock_session.call_tool.return_value = CallToolResult(
        content=[TextContent(type="text", text="")],
        isError=False,
    )

    with patch(
        "cleankoda.commands.cmd_issue_to_plan.connect_mcp_server",
        new_callable=AsyncMock,
        return_value=(mock_exit_stack, mock_session),
    ):
        res = await cmd_issue_to_plan([], ctx)
        assert res.output == "No open cards found in the 'Todo' list."


@pytest.mark.anyio
async def test_cmd_issue_to_plan_interactive_cancel():
    mock_memory = MagicMock()
    ctx = CommandContext(memory=mock_memory)

    mock_exit_stack = AsyncMock()
    mock_session = AsyncMock()
    mock_session.call_tool.return_value = CallToolResult(
        content=[TextContent(type="text", text="- [c1] Story 1: Desc 1...")],
        isError=False,
    )

    with (
        patch(
            "cleankoda.commands.cmd_issue_to_plan.connect_mcp_server",
            new_callable=AsyncMock,
            return_value=(mock_exit_stack, mock_session),
        ),
        patch(
            "cleankoda.commands.cmd_issue_to_plan.select_issue_interactive",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        res = await cmd_issue_to_plan([], ctx)
        assert res.output == "Ticket selection cancelled."


@pytest.mark.anyio
async def test_cmd_issue_to_plan_mcp_error():
    mock_memory = MagicMock()
    ctx = CommandContext(memory=mock_memory)

    mock_exit_stack = AsyncMock()
    mock_session = AsyncMock()
    mock_session.call_tool.side_effect = RuntimeError("MCP connection error")

    with patch(
        "cleankoda.commands.cmd_issue_to_plan.connect_mcp_server",
        new_callable=AsyncMock,
        return_value=(mock_exit_stack, mock_session),
    ):
        res = await cmd_issue_to_plan(["bad_id"], ctx)
        assert res.output is not None
        assert "Error fetching ticket details" in res.output
