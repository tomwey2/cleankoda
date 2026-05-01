"""
Abstract interface for external version control system integrations.

This module defines the contract that all version control systems (GitHub, GitLab, Bitbucket, etc.)
must implement. It provides domain models that are independent of any specific
version control system implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PullRequest:  # pylint: disable=too-many-instance-attributes
    """Represents a GitHub Pull Request."""

    number: int
    title: str
    body: str
    html_url: str
    state: str
    head_branch: str
    base_branch: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class PRReview:
    """Represents a GitHub Pull Request review."""

    id: str
    reviewer: str
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED
    body: str
    submitted_at: str


@dataclass(frozen=True)
class PRReviewComment:
    """Represents a line-level code review comment on a PR."""

    id: str
    reviewer: str
    body: str
    path: str | None
    start_line: int | None
    end_line: int | None
    created_at: str


class VersionControlSystem(ABC):
    """
    Abstract interface for external version control system operations.

    All version control systems (GitHub,GitLab, Bitbucket, etc.) must implement
    this interface to ensure consistent behavior across different systems.
    """

    @abstractmethod
    def get_default_branch_name(self) -> str:
        """
        Get the default branch name (e.g. "main" or "master") for the repository.
        Returns:
            The default branch name as a string
        """

    @abstractmethod
    async def create_pull_request(self, title: str, body: str, source_branch: str) -> PullRequest:
        """
        Create a pull request for the given title, body and source branch.
        Args:
            title: The title of the pull request
            body: The body of the pull request
            source_branch: The source branch of the pull request (to be merged to default branch)
        Returns:
            The created PullRequest object
        """

    @abstractmethod
    async def add_comment_to_pr(self, repo_pr_number: int, comment: str) -> None:
        """
        Add a comment to a pull request.
        Args:
            repo_pr_number: The number of the pull request
            comment: The comment text to add
        """

    @abstractmethod
    async def get_pr(self, repo_pr_number: int) -> PullRequest:
        """
        Get the details of a pull request.
        Args:
            repo_pr_number: The number of the pull request
        Returns:
            The details of the pull request
        """

    @abstractmethod
    async def get_pr_reviews(self, repo_pr_number: int) -> list[PRReview]:
        """
        Get the reviews on a pull request.
        Args:
            repo_pr_number: The number of the pull request
        Returns:
            A list of reviews on the pull request
        """

    @abstractmethod
    async def get_pr_review_comments(self, repo_pr_number: int) -> list[PRReviewComment]:
        """
        Get the review comments on a pull request.
        Args:
            repo_pr_number: The number of the pull request
        Returns:
            A list of comments on the pull request
        """

    @abstractmethod
    async def get_pr_review_status(
        self, repo_pr_number: int
    ) -> tuple[bool, list[PRReview], list[PRReviewComment]]:
        """
        Get the review status of a pull request.
        Args:
            repo_pr_number: The number of the pull request
        Returns:
            A tuple containing:
            - bool: True if the pull request is approved, False otherwise
            - list[PRReview]: A list of reviews on the pull request
            - list[PRReviewComment]: A list of comments on the pull request
        """

    @abstractmethod
    def format_pr_review_status(
        self,
        repo_pr_url: str,
        rejection_reviews: list[PRReview],
        code_comments: list[PRReviewComment],
    ) -> str:
        """
        Format PR review status as a human-readable message.

        Args:
            repo_pr_url: URL of the pull request
            rejection_reviews: List of reviews with CHANGES_REQUESTED state
            code_comments: List of line-level code review comments

        Returns:
            Formatted string for display
        """
