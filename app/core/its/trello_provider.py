"""
Trello implementation of the IssueProvider interface.

This adapter wraps the existing Trello client functions and adapts them
to the IssueProvider interface, allowing Trello to be used interchangeably
with other issue tracking systems.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.its.issue_tracking_system import (
    IssueTrackingSystem,
    Issue,
    IssueComment,
    IssueStateMove,
)
from app.core.its.trello_client import (
    add_comment_to_trello_card,
    create_trello_card,
    get_all_trello_cards,
    get_all_trello_lists,
    get_trello_card,
    get_trello_card_comments,
    get_trello_card_list_moves,
    move_trello_card_to_list,
    move_trello_card_to_named_list,
)
from app.core.localdb.models import AgentSettingsDb
from app.core.types import IssueSystemType

logger = logging.getLogger(__name__)


class TrelloProvider(IssueTrackingSystem):
    """
    Trello implementation of the IssueProvider interface.

    This class wraps the existing Trello client functions and provides
    a consistent interface for issue operations.
    """

    def __init__(self, agent_settings: AgentSettingsDb):
        """
        Initialize the Trello provider.

        Args:
            agent_settings: Agent settings containing Trello credentials and settings
        """
        self.agent_settings = agent_settings

    async def get_states(self) -> list[dict]:
        """Fetch all states (Trello lists) from the board."""
        return await get_all_trello_lists(self.agent_settings)

    async def get_issue(self, issue_id: str) -> Optional[Issue]:
        """Fetch a specific Trello card."""
        card = await get_trello_card(issue_id, self.agent_settings)

        if not card:
            logger.warning("Trello card %s not found", issue_id)
            return None

        return Issue(
            id=card["id"],
            name=card.get("name", ""),
            description=card.get("desc", ""),
            state_id=card.get("list_id", ""),
            state_name=card.get("list_name", ""),
            url=card.get("url", ""),
        )

    async def get_issues_from_state(self, state_id: str) -> list[Issue]:
        """Fetch all issues from a specific state (Trello list)."""
        # state_id corresponds to Trello list_id
        state_name = await self._resolve_state_name_from_id(state_id)
        cards = await get_all_trello_cards(state_id, self.agent_settings)

        return [
            Issue(
                id=card["id"],
                name=card["name"],
                description=card["desc"],
                state_id=state_id,
                state_name=state_name,
                url=card.get("url", ""),
            )
            for card in cards
        ]

    async def _resolve_state_name_from_id(self, state_id: str) -> str:
        """Resolve the human-readable Trello list name for a given list ID."""
        try:
            trello_lists = await get_all_trello_lists(self.agent_settings)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("Failed to resolve Trello state name for %s: %s", state_id, exc)
            return ""

        for trello_list in trello_lists:
            if trello_list["id"] == state_id:
                return trello_list.get("name", "")

        logger.warning("Trello list %s not found when resolving state name", state_id)
        return ""

    async def move_issue_to_state(self, issue_id: str, state_id: str) -> None:
        """Move a issue to a different state (Trello list)."""
        # state_id corresponds to Trello list_id
        await move_trello_card_to_list(issue_id, state_id, self.agent_settings)

    async def move_issue_to_named_state(self, issue_id: str, state_name: str) -> str:
        """Move a issue to a state (Trello list) identified by name."""
        # state_name corresponds to Trello list_name
        return await move_trello_card_to_named_list(issue_id, state_name, self.agent_settings)

    async def add_comment(self, issue_id: str, comment: str) -> None:
        """Add a comment to a Trello issue."""
        await add_comment_to_trello_card(issue_id, comment, self.agent_settings)

    async def get_comments(self, issue_id: str) -> list[IssueComment]:
        """Fetch all comments for a Trello issue."""
        comments = await get_trello_card_comments(issue_id, self.agent_settings)

        return [
            IssueComment(
                id=comment["id"],
                text=comment["text"],
                author=comment["member_creator"],
                date=self._parse_timestamp(comment["date"]),
            )
            for comment in comments
        ]

    async def get_state_moves(self, issue_id: str) -> list[IssueStateMove]:
        """Fetch the history of state moves (Trello list moves) for an issue."""
        moves = await get_trello_card_list_moves(issue_id, self.agent_settings)

        return [
            IssueStateMove(
                id=move["id"],
                date=self._parse_timestamp(move["date"]),
                state_before=move["list_before"],
                state_after=move["list_after"],
            )
            for move in moves
        ]

    async def create_issue(self, name: str, description: str, state_name: str) -> Issue:
        """Create a new issue in the specified state (Trello list)."""
        # state_name corresponds to Trello list_name
        result = await create_trello_card(
            name,
            description,
            state_name,
            self.agent_settings,
        )

        return Issue(
            id=result["id"],
            name=result["name"],
            description=description,
            state_id="",
            state_name=result["list"],
            url=result.get("url", ""),
        )

    def get_type(self) -> str:
        """Return the provider identifier."""
        return IssueSystemType.TRELLO

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

    def get_state_todo(self) -> str:
        return self.agent_settings.its_state_todo

    def get_state_in_progress(self) -> str:
        return self.agent_settings.its_state_in_progress

    def get_state_in_review(self) -> str:
        return self.agent_settings.its_state_in_review

    def get_state_done(self) -> str:
        return self.agent_settings.its_state_done
