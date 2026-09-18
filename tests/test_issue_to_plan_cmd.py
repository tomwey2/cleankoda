from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from cleankoda.commands import CommandContext
from cleankoda.commands.cmd_issue_to_plan import (
    cmd_issue_to_plan,
    extract_trello_card_id,
)
from cleankoda.its.its import Issue


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


@pytest.mark.anyio
async def test_cmd_issue_to_plan_with_card_id_arg():
    mock_memory = MagicMock()
    ctx = CommandContext(memory=mock_memory)

    mock_issue = Issue(
        id="card123",
        title="Add Feature X",
        description="Feature X description",
        state_id="todo_list",
        state_name="Todo",
    )

    with patch("cleankoda.commands.cmd_issue_to_plan.TrelloClient") as mock_trello_cls:
        mock_trello = MagicMock()
        mock_trello.get_issue = AsyncMock(return_value=mock_issue)
        mock_trello_cls.return_value = mock_trello

        res = await cmd_issue_to_plan(["card123"], ctx)

        mock_trello.get_issue.assert_called_once_with("card123")
        assert res.output is not None
        assert "Ticket: Add Feature X" in res.output
        assert "Feature X description" in res.output
        mock_memory.add_user.assert_called_once()


@pytest.mark.anyio
async def test_cmd_issue_to_plan_with_url_arg():
    mock_memory = MagicMock()
    ctx = CommandContext(memory=mock_memory)

    mock_issue = Issue(
        id="CardShortlink",
        title="URL Story",
        description="URL Story description",
        state_id="todo_list",
        state_name="Todo",
    )

    with patch("cleankoda.commands.cmd_issue_to_plan.TrelloClient") as mock_trello_cls:
        mock_trello = MagicMock()
        mock_trello.get_issue = AsyncMock(return_value=mock_issue)
        mock_trello_cls.return_value = mock_trello

        res = await cmd_issue_to_plan(
            ["https://trello.com/c/CardShortlink/story-title"], ctx
        )

        mock_trello.get_issue.assert_called_once_with("CardShortlink")
        assert res.output is not None
        assert "Ticket: URL Story" in res.output


@pytest.mark.anyio
async def test_cmd_issue_to_plan_interactive_selection():
    mock_memory = MagicMock()
    ctx = CommandContext(memory=mock_memory)

    mock_issues = [
        Issue(
            id="c1",
            title="Story 1",
            description="Desc 1",
            state_id="todo",
            state_name="Todo",
        ),
        Issue(
            id="c2",
            title="Story 2",
            description="Desc 2",
            state_id="todo",
            state_name="Todo",
        ),
    ]

    with (
        patch("cleankoda.commands.cmd_issue_to_plan.TrelloClient") as mock_trello_cls,
        patch(
            "cleankoda.commands.cmd_issue_to_plan.select_issue_interactive",
            new_callable=AsyncMock,
        ) as mock_select,
    ):
        mock_trello = MagicMock()
        mock_trello.get_issues_from_state = AsyncMock(return_value=mock_issues)
        mock_trello.get_issue = AsyncMock(return_value=mock_issues[1])
        mock_trello_cls.return_value = mock_trello

        mock_select.return_value = "c2"

        res = await cmd_issue_to_plan([], ctx)

        mock_select.assert_called_once_with(ctx, mock_issues)
        mock_trello.get_issue.assert_called_once_with("c2")
        assert res.output is not None
        assert "Ticket: Story 2" in res.output


@pytest.mark.anyio
async def test_cmd_issue_to_plan_empty_todo_list():
    mock_memory = MagicMock()
    ctx = CommandContext(memory=mock_memory)

    with patch("cleankoda.commands.cmd_issue_to_plan.TrelloClient") as mock_trello_cls:
        mock_trello = MagicMock()
        mock_trello.get_issues_from_state = AsyncMock(return_value=[])
        mock_trello_cls.return_value = mock_trello

        res = await cmd_issue_to_plan([], ctx)

        assert res.output == "No open cards found in the 'Todo' list."


@pytest.mark.anyio
async def test_cmd_issue_to_plan_interactive_cancel():
    mock_memory = MagicMock()
    ctx = CommandContext(memory=mock_memory)
    mock_issues = [
        Issue(
            id="c1",
            title="Story 1",
            description="Desc 1",
            state_id="todo",
            state_name="Todo",
        )
    ]

    with (
        patch("cleankoda.commands.cmd_issue_to_plan.TrelloClient") as mock_trello_cls,
        patch(
            "cleankoda.commands.cmd_issue_to_plan.select_issue_interactive",
            new_callable=AsyncMock,
        ) as mock_select,
    ):
        mock_trello = MagicMock()
        mock_trello.get_issues_from_state = AsyncMock(return_value=mock_issues)
        mock_trello_cls.return_value = mock_trello

        mock_select.return_value = None

        res = await cmd_issue_to_plan([], ctx)

        assert res.output == "Ticket selection cancelled."


@pytest.mark.anyio
async def test_cmd_issue_to_plan_trello_error():
    mock_memory = MagicMock()
    ctx = CommandContext(memory=mock_memory)

    with patch("cleankoda.commands.cmd_issue_to_plan.TrelloClient") as mock_trello_cls:
        mock_trello = MagicMock()
        mock_trello.get_issue = AsyncMock(
            side_effect=RuntimeError("Trello API 404 Not Found")
        )
        mock_trello_cls.return_value = mock_trello

        res = await cmd_issue_to_plan(["bad_id"], ctx)

        assert res.output is not None
        assert "Error fetching ticket 'bad_id'" in res.output
