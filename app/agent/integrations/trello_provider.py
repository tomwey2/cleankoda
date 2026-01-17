"""
Trello implementation of the BoardProvider interface.

This adapter wraps the existing Trello client functions and adapts them
to the BoardProvider interface, allowing Trello to be used interchangeably
with other board systems.
"""

import logging
from datetime import datetime, timezone

from agent.integrations.board_provider import (
    BoardTask,
    BoardComment,
    BoardListMove,
    BoardProvider,
)
from agent.integrations.trello_client import (
    add_comment_to_trello_card,
    create_trello_card,
    get_all_trello_cards,
    get_all_trello_lists,
    get_trello_card_comments,
    get_trello_card_list_moves,
    move_trello_card_to_list,
    move_trello_card_to_named_list,
)

logger = logging.getLogger(__name__)


class TrelloProvider(BoardProvider):
    """
    Trello implementation of the BoardProvider interface.
    
    This class wraps the existing Trello client functions and provides
    a consistent interface for board operations.
    """

    def __init__(self, sys_config: dict):
        """
        Initialize the Trello provider.
        
        Args:
            sys_config: System configuration containing Trello credentials and settings
        """
        self.sys_config = sys_config

    async def get_lists(self) -> list[dict]:
        """Fetch all lists from the Trello board."""
        return await get_all_trello_lists(self.sys_config)

    async def get_tasks_from_list(self, list_id: str) -> list[BoardTask]:
        """Fetch all tasks from a specific Trello list."""
        cards = await get_all_trello_cards(list_id, self.sys_config)

        return [
            BoardTask(
                id=card["id"],
                name=card["name"],
                description=card["desc"],
                list_id=list_id,
                list_name="",
                url=card.get("url", ""),
            )
            for card in cards
        ]

    async def move_task_to_list(self, task_id: str, list_id: str) -> None:
        """Move a Trello task to a different list."""
        await move_trello_card_to_list(task_id, list_id, self.sys_config)

    async def move_task_to_named_list(self, task_id: str, list_name: str) -> str:
        """Move a Trello task to a list identified by name."""
        return await move_trello_card_to_named_list(
            task_id, list_name, self.sys_config
        )

    async def add_comment(self, task_id: str, comment: str) -> None:
        """Add a comment to a Trello task."""
        await add_comment_to_trello_card(task_id, comment, self.sys_config)

    async def get_comments(self, task_id: str) -> list[BoardComment]:
        """Fetch all comments for a Trello task."""
        comments = await get_trello_card_comments(task_id, self.sys_config)

        return [
            BoardComment(
                id=comment["id"],
                text=comment["text"],
                author=comment["member_creator"],
                date=self._parse_timestamp(comment["date"]),
            )
            for comment in comments
        ]

    async def get_list_moves(self, task_id: str) -> list[BoardListMove]:
        """Fetch the history of list moves for a Trello task."""
        moves = await get_trello_card_list_moves(task_id, self.sys_config)

        return [
            BoardListMove(
                id=move["id"],
                date=self._parse_timestamp(move["date"]),
                list_before=move["list_before"],
                list_after=move["list_after"],
            )
            for move in moves
        ]

    async def create_task(
        self, name: str, description: str, list_name: str
    ) -> BoardTask:
        """Create a new Trello task in the specified list."""
        result = await create_trello_card(name, description, list_name, self.sys_config)

        return BoardTask(
            id=result["id"],
            name=result["name"],
            description=description,
            list_id="",
            list_name=result["list"],
            url=result.get("url", ""),
        )

    def _parse_timestamp(self, value: str | None) -> datetime:
        """
        Parse a Trello timestamp string into a datetime object.
        
        Args:
            value: ISO format timestamp string
            
        Returns:
            Parsed datetime object with timezone info
        """
        if not value:
            return datetime.now(timezone.utc)

        normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            logger.warning("Failed to parse Trello timestamp '%s'", value)
            return datetime.now(timezone.utc)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed
