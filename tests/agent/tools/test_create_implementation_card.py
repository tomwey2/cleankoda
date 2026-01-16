"""Unit tests for create_implementation_card tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import anyio

from agent.tools.create_implementation_card import create_implementation_card_tool


def test_create_implementation_card_tool_creates_card_successfully():
    """Test that the tool creates a card successfully with valid config."""
    async def _test():
        sys_config = {
            "trello_readfrom_list": "Sprint Backlog",
            "env": {
                "TRELLO_API_KEY": "test_key",
                "TRELLO_TOKEN": "test_token",
            },
        }

        mock_card_data = {
            "id": "card123",
            "name": "Add Feature X",
            "url": "https://trello.com/c/card123",
            "list": "Sprint Backlog",
        }

        with patch(
            "agent.tools.create_implementation_card.create_trello_card",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = mock_card_data

            tool = create_implementation_card_tool(sys_config)
            result = await tool.ainvoke(
                {
                    "title": "Add Feature X",
                    "instructions": "Implement feature X with proper tests",
                }
            )

            # Verify the Trello API was called correctly
            mock_create.assert_called_once_with(
                name="Add Feature X",
                description="Implement feature X with proper tests",
                list_name="Sprint Backlog",
                sys_config=sys_config,
            )

            # Verify the result message
            assert "Successfully created implementation card" in result
            assert "Add Feature X" in result
            assert "https://trello.com/c/card123" in result
            assert "Sprint Backlog" in result

    anyio.run(_test)


def test_create_implementation_card_tool_handles_missing_config():
    """Test that the tool handles missing trello_readfrom_list config."""
    async def _test():
        sys_config = {
            "env": {
                "TRELLO_API_KEY": "test_key",
                "TRELLO_TOKEN": "test_token",
            },
        }

        tool = create_implementation_card_tool(sys_config)
        result = await tool.ainvoke(
            {
                "title": "Test Task",
                "instructions": "Test instructions",
            }
        )

        assert "Error: trello_readfrom_list not configured" in result

    anyio.run(_test)


def test_create_implementation_card_tool_handles_value_error():
    """Test that the tool handles ValueError from Trello client."""
    async def _test():
        sys_config = {
            "trello_readfrom_list": "Invalid List",
            "env": {
                "TRELLO_API_KEY": "test_key",
                "TRELLO_TOKEN": "test_token",
            },
        }

        with patch(
            "agent.tools.create_implementation_card.create_trello_card",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.side_effect = ValueError("List 'Invalid List' not found")

            tool = create_implementation_card_tool(sys_config)
            result = await tool.ainvoke(
                {
                    "title": "Test Task",
                    "instructions": "Test instructions",
                }
            )

            assert "Error:" in result
            assert "List 'Invalid List' not found" in result

    anyio.run(_test)


def test_create_implementation_card_tool_handles_runtime_error():
    """Test that the tool handles RuntimeError from Trello API."""
    async def _test():
        sys_config = {
            "trello_readfrom_list": "Sprint Backlog",
            "env": {
                "TRELLO_API_KEY": "test_key",
                "TRELLO_TOKEN": "test_token",
            },
        }

        with patch(
            "agent.tools.create_implementation_card.create_trello_card",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.side_effect = RuntimeError("Failed to create card: API error")

            tool = create_implementation_card_tool(sys_config)
            result = await tool.ainvoke(
                {
                    "title": "Test Task",
                    "instructions": "Test instructions",
                }
            )

            assert "Failed to create card:" in result
            assert "API error" in result

    anyio.run(_test)


def test_create_implementation_card_tool_has_correct_metadata():
    """Test that the tool has correct name and description."""
    sys_config = {"trello_readfrom_list": "To Do"}

    tool = create_implementation_card_tool(sys_config)

    assert tool.name == "create_implementation_card"
    assert "Creates a new Trello card" in tool.description
    assert "implementation instructions" in tool.description


def test_create_implementation_card_tool_binds_sys_config():
    """Test that the factory function correctly binds sys_config via closure."""
    async def _test():
        sys_config_1 = {"trello_readfrom_list": "List A"}
        sys_config_2 = {"trello_readfrom_list": "List B"}

        mock_card_data = {
            "id": "card123",
            "name": "Test",
            "url": "https://trello.com/c/card123",
            "list": "List A",
        }

        with patch(
            "agent.tools.create_implementation_card.create_trello_card",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = mock_card_data

            tool_1 = create_implementation_card_tool(sys_config_1)
            tool_2 = create_implementation_card_tool(sys_config_2)

            # Call tool_1
            await tool_1.ainvoke({"title": "Task 1", "instructions": "Instructions 1"})

            # Verify it used sys_config_1
            call_args = mock_create.call_args
            assert call_args[1]["list_name"] == "List A"
            assert call_args[1]["sys_config"] == sys_config_1

            mock_create.reset_mock()
            mock_card_data["list"] = "List B"
            mock_create.return_value = mock_card_data

            # Call tool_2
            await tool_2.ainvoke({"title": "Task 2", "instructions": "Instructions 2"})

            # Verify it used sys_config_2
            call_args = mock_create.call_args
            assert call_args[1]["list_name"] == "List B"
            assert call_args[1]["sys_config"] == sys_config_2

    anyio.run(_test)
