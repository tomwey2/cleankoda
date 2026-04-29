"""
GitHub Projects v2 implementation of the IssueProvider interface.

This module provides a GitHubProvider class that wraps the GitHub Projects v2
GraphQL API client and implements the IssueProvider interface for consistent
issue operations across different systems.
"""

import logging
from datetime import datetime, timezone

from src.core.its.issue_tracking_system import (
    IssueComment,
    IssueTrackingSystem,
    Issue,
)
from src.core.its.github_client import (
    add_comment_to_gh_issue,
    create_draft_issue,
    get_comments_from_gh_issue,
    get_items_from_column,
    get_project_columns,
    get_project_item,
    move_item_to_column,
)
from src.core.database.models import AgentSettingsDb
from src.core.types import IssueStateType

logger = logging.getLogger(__name__)


class GitHubIts(IssueTrackingSystem):
    """
    GitHub Projects v2 implementation of the IssueTrackingSystem interface.

    This class wraps the GitHub GraphQL API client functions and provides
    a consistent interface for issue operations.
    """

    def __init__(self, agent_settings: AgentSettingsDb):
        """
        Initialize the GitHub provider.

        Args:
            agent_settings: Agent settings containing GitHub project configuration.
        """
        self.agent_settings = agent_settings

    async def get_states(self) -> list[dict]:
        """Fetch all states (columns) from the GitHub Project."""
        return await get_project_columns(self.agent_settings)

    async def get_issue_by_id(self, issue_id: str) -> Issue | None:
        """Fetch a specific issue (project item) by ID."""
        item = await get_project_item(issue_id, self.agent_settings)

        if not item:
            logger.warning("GitHub Issue %s not found", issue_id)
            return None

        state_type = self.agent_settings.translate_issue_state_to_type(item.get("state_name", ""))
        if state_type == IssueStateType.UNKNOWN:
            logger.warning("Could not determine state for card %s", issue_id)

        return Issue(
            id=item["id"],
            name=item.get("title", ""),
            description=item.get("body", ""),
            state_type=state_type,
            state_id=item.get("state_id", ""),
            state_name=item.get("state_name", ""),
            url=item.get("url", ""),
        )

    async def get_issues_from_state(self, state_type: IssueStateType) -> list[Issue]:
        """
        Fetch all issues from a specific state (column).

        Note: For GitHub Projects, we need to resolve the column name from ID
        first, then fetch items. The state_id here is the column option ID.
        """
        state_id = self.agent_settings.translate_type_to_issue_state(state_type)
        columns = await get_project_columns(self.agent_settings)
        target_column = next((col for col in columns if col["id"] == state_id), None)

        if not target_column:
            logger.warning("Column with ID %s not found", state_id)
            return []

        items = await get_items_from_column(target_column["name"], self.agent_settings)

        return [
            Issue(
                id=item["id"],
                name=item["title"],
                description=item["body"] or "",
                state_type=state_type,
                state_id=state_id,
                state_name=target_column["name"],
                url=item.get("url", ""),
            )
            for item in items
        ]

    async def move_issue_to_state(self, issue_id: str, target_state_type: IssueStateType) -> None:
        """Move a issue to a different state (column)."""
        state_id = self.agent_settings.translate_type_to_issue_state(target_state_type)
        await move_item_to_column(issue_id, state_id, self.agent_settings)

    async def add_comment_to_issue(self, issue_id: str, comment: str) -> None:
        """
        Add a comment to a GitHub issue.

        Note: For GitHub Projects, we need the issue ID (content_id), not the
        project item ID. If the issue_id is a project item ID, we need to
        extract the content ID first.
        """
        await add_comment_to_gh_issue(issue_id, comment, self.agent_settings)

    async def get_comments_from_issue(self, issue_id: str) -> list[IssueComment]:
        """Fetch all comments for a GitHub issue."""
        comments = await get_comments_from_gh_issue(issue_id, self.agent_settings)

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
        """Create a new issue (draft issue) in the specified state (column)."""
        result = await create_draft_issue(
            name,
            description,
            state_name,
            self.agent_settings,
        )

        return Issue(
            id=result["id"],
            name=result["title"],
            description=description,
            state_id="",
            state_name=result["column"],
            url=result.get("url", ""),
        )

    def get_type(self) -> str:
        """Return the provider identifier."""
        return "github"

    def _parse_timestamp(self, value: str | None) -> datetime:
        """
        Parse a GitHub timestamp string into a datetime object.

        Args:
            value: ISO format timestamp string.

        Returns:
            Parsed datetime object with timezone info.
        """
        if not value:
            return datetime.now(timezone.utc)

        normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            logger.warning("Failed to parse GitHub timestamp '%s'", value)
            return datetime.now(timezone.utc)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed
