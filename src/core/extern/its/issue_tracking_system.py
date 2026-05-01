"""
Abstract interface for external issue tracking system integrations.

This module defines the contract that all issue tracking system (Trello, GitHub Issues, Jira, etc.)
must implement. It provides domain models that are independent of any specific
issue tracking system implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from src.core.types import IssueStateType


@dataclass
class Issue:
    """
    Domain model for a issue, independent of the issue tracking system.

    Attributes:
        id: Unique identifier for the issue
        name: Title/name of the issue
        description: Detailed description of the issue
        state_id: ID of the state/column containing this issue
        state_name: Name of the state/column containing this issue
        url: URL to view the issue in the issue system
    """

    id: str
    name: str
    description: str
    state_type: IssueStateType
    state_id: str
    state_name: str
    url: str = ""


@dataclass
class IssueComment:
    """
    Domain model for a comment on a issue.

    Attributes:
        id: Unique identifier for the comment
        text: Content of the comment
        author: Name of the comment author
        date: Timestamp when the comment was created
    """

    id: str
    text: str
    author: str
    date: datetime

    def __str__(self):
        return f"{self.author}: {self.text} ({self.date.isoformat()})"


class IssueTrackingSystem(ABC):
    """
    Abstract interface for external issue tracking system operations.

    All issue tracking systems (Trello, GitHub Issues, Jira, etc.) must implement
    this interface to ensure consistent behavior across different systems.
    """

    @abstractmethod
    async def get_issue_by_id(self, issue_id: str) -> Issue | None:
        """
        Fetch a specific issue from the issue system.

        Args:
            issue_id: The ID of the issue to fetch

        Returns:
            The Issue object

        Raises:
            RuntimeError: If issue fetching fails
        """

    @abstractmethod
    async def get_next_issue_from_state(self, state_type: IssueStateType) -> Issue | None:
        """
        Fetch the next issue from a specific state.

        Args:
            state_type: The type of the state to fetch issues from

        Returns:
            The Issue object or None if no issues are found

        Raises:
            RuntimeError: If fetching issues fails
        """

    @abstractmethod
    async def move_issue_to_state(self, issue_id: str, target_state_type: IssueStateType) -> None:
        """
        Move a issue to a different state.

        Args:
            issue_id: The ID of the issue to move
            state_type: The type of the target state

        Raises:
            RuntimeError: If the operation fails
        """

    @abstractmethod
    async def add_comment_to_issue(self, issue_id: str, comment: str) -> None:
        """
        Add a comment to a issue.

        Args:
            issue_id: The ID of the issue
            comment: The comment text to add

        Raises:
            RuntimeError: If adding the comment fails
        """

    @abstractmethod
    async def get_comments_from_issue(self, issue_id: str) -> list[IssueComment]:
        """
        Fetch all comments for a issue.

        Args:
            issue_id: The ID of the issue

        Returns:
            List of IssueComment objects

        Raises:
            RuntimeError: If fetching comments fails
        """

    @abstractmethod
    async def create_issue(self, name: str, description: str, state_name: str) -> Issue:
        """
        Create a new issue in the specified state.

        Args:
            name: The title/name of the issue
            description: The description/body of the issue
            state_name: The name of the state to create the issue in

        Returns:
            The created Issue object

        Raises:
            ValueError: If the state name is not found
            RuntimeError: If issue creation fails
        """

    @abstractmethod
    def get_type(self) -> str:
        """Return provider identifier (e.g., 'TRELLO', 'GITHUB')."""
