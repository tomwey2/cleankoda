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


class VersionControlSystem(ABC):
    """
    Abstract interface for external version control system operations.

    All version control systems (GitHub,GitLab, Bitbucket, etc.) must implement
    this interface to ensure consistent behavior across different systems.
    """

    @abstractmethod
    def get_default_branch_name(self) -> str:
        pass

    @abstractmethod
    async def create_pull_request(self, title: str, source_branch: str) -> PullRequest:
        # to target_branch (from settings)
        pass

    @abstractmethod
    async def add_comment_to_pr(self, pr_number: int, comment: str) -> None:
        pass
