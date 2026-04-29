"""
Trello implementation of the IssueProvider interface.

This adapter wraps the existing Trello client functions and adapts them
to the IssueProvider interface, allowing Trello to be used interchangeably
with other issue tracking systems.
"""

import logging
from datetime import datetime, timezone

from src.core.its.issue_tracking_system import (
    IssueTrackingSystem,
    Issue,
    IssueComment,
)
from src.core.its.trello_client import (
    add_comment_to_trello_card,
    create_trello_card,
    get_all_trello_cards,
    get_all_trello_lists,
    get_trello_card,
    get_comments_from_trello_card,
    move_trello_card_to_list,
)
from src.core.database.models import AgentSettingsDb
from src.core.types import IssueTrackingSystemType, IssueStateType

logger = logging.getLogger(__name__)


class TrelloIts(IssueTrackingSystem):
    """
    Trello implementation of the IssueTrackingSystem interface.

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

    async def get_issue_by_id(self, issue_id: str) -> Issue | None:
        """Fetch a specific Trello card."""
        card = await get_trello_card(issue_id, self.agent_settings)

        if not card:
            logger.warning("Trello card %s not found", issue_id)
            return None

        state_type = self.agent_settings.translate_issue_state_to_type(card.get("list_name", ""))
        if state_type == IssueStateType.UNKNOWN:
            logger.warning("Could not determine state for card %s", issue_id)

        return Issue(
            id=card["id"],
            name=card.get("name", ""),
            description=card.get("desc", ""),
            state_type=state_type,
            state_id=card.get("list_id", ""),
            state_name=card.get("list_name", ""),
            url=card.get("url", ""),
        )

    async def get_next_issue_from_state(self, state_type: IssueStateType) -> Issue | None:
        """Fetch the next issue from a specific state (Trello list)."""
        state_id, state_name = await self._resolve_trello_state_from_state_type(state_type)
        cards = await get_all_trello_cards(state_id, self.agent_settings)

        if not cards:
            logger.warning("No issues found in state %s", state_name)
            return None

        card = cards[0]
        return Issue(
            id=card["id"],
            name=card.get("name", ""),
            description=card.get("desc", ""),
            state_type=state_type,
            state_id=state_id,
            state_name=state_name,
            url=card.get("url", ""),
        )

    async def _resolve_trello_state_from_state_type(
        self, state_type: IssueStateType
    ) -> tuple[str, str]:
        """Resolve the human-readable Trello list name for a given list ID."""
        state_name = self.agent_settings.translate_type_to_issue_state(state_type)
        try:
            trello_lists = await get_all_trello_lists(self.agent_settings)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("Failed to resolve Trello state name for %s: %s", state_name, exc)
            return "", ""

        for trello_list in trello_lists:
            if trello_list["name"] == state_name:
                return trello_list.get("id", ""), trello_list.get("name", "")

        logger.warning("Trello list %s not found when resolving state name", state_name)
        return "", ""

    async def move_issue_to_state(self, issue_id: str, target_state_type: IssueStateType) -> None:
        """Move a issue to a different state (Trello list)."""
        target_state_id, target_state_name = await self._resolve_trello_state_from_state_type(
            target_state_type
        )

        if not target_state_id:
            raise ValueError(
                f"Trello list {target_state_name} ({target_state_type.name}) not found on configured board"
            )

        await move_trello_card_to_list(issue_id, target_state_id, self.agent_settings)

    async def add_comment_to_issue(self, issue_id: str, comment: str) -> None:
        """Add a comment to a Trello issue."""
        await add_comment_to_trello_card(issue_id, comment, self.agent_settings)

    async def get_comments_from_issue(self, issue_id: str) -> list[IssueComment]:
        """Fetch all comments for a Trello issue."""
        comments = await get_comments_from_trello_card(issue_id, self.agent_settings)

        return [
            IssueComment(
                id=comment["id"],
                text=comment["text"],
                author=comment["member_creator"],
                date=self._parse_timestamp(comment["date"]),
            )
            for comment in comments
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
        return IssueTrackingSystemType.TRELLO

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
