"""
Dataclasses for node operation results.

These models improve code readability by replacing complex tuples with
named, typed structures.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.integrations.board_provider import BoardTask


@dataclass
class TaskResolveResult:
    """Result of resolving which task to work on."""

    task: "BoardTask | None"
    comments: list
    pr_review_message: str
    git_branch: str | None


@dataclass
class PRCreationResult:
    """Result of PR creation/update operation."""

    success: bool
    message: str
    pr_url: str | None = None
    pr_number: int | None = None


@dataclass
class GitOperationResult:
    """Result of a git operation (add, commit, push)."""

    success: bool
    message: str


@dataclass
class PRReviewInfo:
    """Information about PR review status."""

    is_approved: bool
    formatted_message: str
    pr_number: int | None = None
    pr_url: str | None = None
