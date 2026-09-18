from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from cleankoda.its.config import IssueState

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
    title: str
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
    async def get_issue(self, issue_id: str) -> Issue | None:
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
    async def get_issues_from_state(self, state: IssueState) -> list[Issue]:
        """
        Fetch all issues from a specific state.

        Args:
            state_id: The ID of the state to fetch issues from

        Returns:
            List of Issue objects
        """

    @abstractmethod
    async def move_issue_to_state(self, issue_id: str, state: IssueState) -> None:
        """
        Move a issue to a different state.

        Args:
            issue_id: The ID of the issue to move
            state: The target state

        Raises:
            RuntimeError: If the operation fails
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
    async def create_issue(self, name: str, description: str, state: IssueState) -> Issue:
        """
        Create a new issue in the specified state.

        Args:
            name: The title/name of the issue
            description: The description/body of the issue
            state: The state to create the issue in

        Returns:
            The created Issue object

        Raises:
            ValueError: If the state name is not found
            RuntimeError: If issue creation fails
        """
