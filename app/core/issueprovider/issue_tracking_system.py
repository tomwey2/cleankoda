"""
Abstract interface for external issue tracking system integrations.

This module defines the contract that all issue tracking system (Trello, GitHub Issues, Jira, etc.)
must implement. It provides domain models that are independent of any specific
issue tracking system implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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


@dataclass
class IssueStateMove:
    """
    Domain model for tracking when a issue moves between states.

    Attributes:
        id: Unique identifier for the move action
        date: Timestamp when the move occurred
        state_before: Name of the state before the move
        state_after: Name of the state after the move
    """

    id: str
    date: datetime
    state_before: str | None
    state_after: str | None


class IssueTrackingSystem(ABC):
    """
    Abstract interface for external issue tracking system operations.

    All issue tracking systems (Trello, GitHub Issues, Jira, etc.) must implement
    this interface to ensure consistent behavior across different systems.
    """

    @abstractmethod
    async def get_states(self) -> list[dict]:
        """
        Fetch all states/columns from the issue system.

        Returns:
            List of dictionaries with 'id' and 'name' keys
        """

    @abstractmethod
    async def get_issue(self, issue_id: str) -> Optional[Issue]:
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
    async def get_issues_from_state(self, state_id: str) -> list[Issue]:
        """
        Fetch all issues from a specific state.

        Args:
            state_id: The ID of the state to fetch issues from

        Returns:
            List of Issue objects
        """

    @abstractmethod
    async def move_issue_to_state(self, issue_id: str, state_id: str) -> None:
        """
        Move a issue to a different state.

        Args:
            issue_id: The ID of the issue to move
            state_id: The ID of the target state

        Raises:
            RuntimeError: If the operation fails
        """

    @abstractmethod
    async def move_issue_to_named_state(self, issue_id: str, state_name: str) -> str:
        """
        Move a issue to a state identified by name.

        Args:
            issue_id: The ID of the issue to move
            state_name: The name of the target state

        Returns:
            The ID of the target state

        Raises:
            ValueError: If the state name is not found
            RuntimeError: If the move operation fails
        """

    @abstractmethod
    async def add_comment(self, issue_id: str, comment: str) -> None:
        """
        Add a comment to a issue.

        Args:
            issue_id: The ID of the issue
            comment: The comment text to add

        Raises:
            RuntimeError: If adding the comment fails
        """

    @abstractmethod
    async def get_comments(self, issue_id: str) -> list[IssueComment]:
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
    async def get_state_moves(self, issue_id: str) -> list[IssueStateMove]:
        """
        Fetch the history of state moves for a issue.

        Args:
            issue_id: The ID of the issue

        Returns:
            List of IssueStateMove objects

        Raises:
            RuntimeError: If fetching move history fails
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

    @abstractmethod
    def get_state_todo(self) -> str:
        """Return the state name for todo."""

    @abstractmethod
    def get_state_in_progress(self) -> str:
        """Return the state name for in progress."""

    @abstractmethod
    def get_state_in_review(self) -> str:
        """Return the state name for in review."""

    @abstractmethod
    def get_state_done(self) -> str:
        """Return the state name for done."""
