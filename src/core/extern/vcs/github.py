"""
GitHub implementation of the VersionControlSystem interface.

This module provides a GitHub VCS class that wraps the GitHub API client and implements
the VersionControlSystem interface for consistent version control operations across different systems.
"""

import httpx

from src.core.database.models import AgentSettingsDb
from src.core.extern.vcs.version_control_system import (
    VersionControlSystem,
    PullRequest,
    PRReviewComment,
    PRReview,
)
from src.core.services.credentials_service import get_credential_by_id


class GitHub(VersionControlSystem):
    """
    GitHub implementation of the VersionControlSystem interface.
    """

    def __init__(self, agent_settings: AgentSettingsDb):
        """
        Initialize the GitHub version control system.

        Args:
            agent_settings: Agent settings containing GitHub project configuration.
        """
        self.agent_settings = agent_settings
        if not self.agent_settings.vcs_credential_id:
            raise ValueError("GitHub credential ID not configured for VCS.")
        self.credential = get_credential_by_id(self.agent_settings.vcs_credential_id)
        if not self.credential or not self.credential.api_token:
            raise ValueError("GitHub token not configured for VCS.")
        if not self.agent_settings.vcs_api_base_url:
            raise ValueError("GitHub API base URL not configured for VCS.")
        if not self.agent_settings.vcs_project_identifier:
            raise ValueError("GitHub project identifier not configured for VCS.")
        if not self.agent_settings.vcs_default_branch:
            raise ValueError("GitHub default branch not configured for VCS.")

    def get_default_branch_name(self) -> str:
        """Get the default branch name for the repository."""
        return self.agent_settings.vcs_default_branch

    def get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.credential.api_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def create_pull_request(self, title: str, body: str, source_branch: str) -> PullRequest:
        """Create a pull request."""
        base_url = self.agent_settings.vcs_api_base_url
        base_url = base_url.rstrip("/")
        repo_id = self.agent_settings.vcs_project_identifier

        url = f"{base_url}/repos/{repo_id}/pulls"
        payload = {
            "title": title,
            "head": source_branch,
            "base": self.get_default_branch_name(),
            "body": f"Pull request created by CleanKoda.\n\n{body}",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, headers=self.get_headers(), json=payload, timeout=30.0
            )

        if response.status_code != 201:
            raise RuntimeError(f"Failed to create pull request: {response.text}")

        data = response.json()
        return PullRequest(
            number=data["number"],
            title=data["title"],
            body=data.get("body", ""),
            html_url=data["html_url"],
            state=data["state"],
            head_branch=data["head"]["ref"],
            base_branch=data["base"]["ref"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    async def add_comment_to_pr(self, repo_pr_number: int, comment: str) -> None:
        """Add a comment to a pull request."""
        base_url = self.agent_settings.vcs_api_base_url
        base_url = base_url.rstrip("/")
        repo_id = self.agent_settings.vcs_project_identifier

        # In GitHub API, PR comments are created via the issues endpoint
        url = f"{base_url}/repos/{repo_id}/issues/{repo_pr_number}/comments"
        payload = {"body": comment}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, headers=self.get_headers(), json=payload, timeout=30.0
            )

        if response.status_code != 201:
            raise RuntimeError(f"Failed to add comment to pull request: {response.text}")

    async def get_pr(self, repo_pr_number: int) -> PullRequest:
        """Get the details of a pull request."""
        base_url = self.agent_settings.vcs_api_base_url
        base_url = base_url.rstrip("/")
        repo_id = self.agent_settings.vcs_project_identifier

        url = f"{base_url}/repos/{repo_id}/pulls/{repo_pr_number}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.get_headers(), timeout=30.0)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to get pull request {repo_pr_number}: {response.text}")

        data = response.json()
        return PullRequest(
            number=data["number"],
            title=data.get("title", ""),
            body=data.get("body", "") or "",
            html_url=data.get("html_url", ""),
            state=data.get("state", ""),
            head_branch=data.get("head", {}).get("ref", ""),
            base_branch=data.get("base", {}).get("ref", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    async def get_pr_reviews(self, repo_pr_number: int) -> list[PRReview]:
        """Get the reviews on a pull request."""
        base_url = self.agent_settings.vcs_api_base_url
        base_url = base_url.rstrip("/")
        repo_id = self.agent_settings.vcs_project_identifier

        url = f"{base_url}/repos/{repo_id}/pulls/{repo_pr_number}/reviews"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.get_headers(), timeout=30.0)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to get pull request {repo_pr_number}: {response.text}")

        data = response.json()
        reviews = [
            PRReview(
                id=str(review_data["id"]),
                reviewer=review_data.get("user", {}).get("login", "unknown"),
                state=review_data.get("state", ""),
                body=review_data.get("body", "") or "",
                submitted_at=review_data.get("submitted_at", ""),
            )
            for review_data in data
        ]
        return reviews

    async def get_pr_review_comments(self, repo_pr_number: int) -> list[PRReviewComment]:
        """Get the review comments on a pull request."""
        base_url = self.agent_settings.vcs_api_base_url
        base_url = base_url.rstrip("/")
        repo_id = self.agent_settings.vcs_project_identifier

        url = f"{base_url}/repos/{repo_id}/pulls/{repo_pr_number}/comments"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.get_headers(), timeout=30.0)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to get pull request {repo_pr_number}: {response.text}")

        comments_data = response.json()
        comments = [
            PRReviewComment(
                id=str(c["id"]),
                reviewer=c.get("user", {}).get("login", "unknown"),
                body=c.get("body", "") or "",
                path=c.get("path"),
                start_line=c.get("start_line") or c.get("original_start_line"),
                end_line=c.get("line") or c.get("original_line"),
                created_at=c.get("created_at", ""),
            )
            for c in comments_data
        ]
        return comments

    async def get_pr_review_status(
        self, repo_pr_number: int
    ) -> tuple[bool, list[PRReview], list[PRReviewComment]]:
        """Get the review status of a pull request."""
        reviews = await self.get_pr_reviews(repo_pr_number)
        comments = await self.get_pr_review_comments(repo_pr_number)

        if not reviews:
            return True, [], comments

        latest_reviews_by_user: dict[str, PRReview] = {}
        for review in reviews:
            if review.state in ("APPROVED", "CHANGES_REQUESTED"):
                existing = latest_reviews_by_user.get(review.reviewer)
                if not existing or review.submitted_at > existing.submitted_at:
                    latest_reviews_by_user[review.reviewer] = review

        rejection_reviews = [
            r for r in latest_reviews_by_user.values() if r.state == "CHANGES_REQUESTED"
        ]

        is_approved = len(rejection_reviews) == 0 and any(
            r.state == "APPROVED" for r in latest_reviews_by_user.values()
        )
        return is_approved, rejection_reviews, comments

    def format_pr_review_status(
        self,
        repo_pr_url: str,
        rejection_reviews: list[PRReview],
        code_comments: list[PRReviewComment],
    ) -> str:
        """Format PR review feedback as a human-readable message."""
        lines = [
            "",
            "=" * 60,
            "PULL REQUEST REVIEW FEEDBACK",
            "=" * 60,
            f"PR: {repo_pr_url}",
            "",
        ]

        def _format_multiline(label: str, text: str) -> list[str]:
            if not text:
                return []
            split_lines = text.splitlines() or [""]
            formatted = [f"{label}{split_lines[0]}"]
            formatted.extend(f"{' ' * len(label)}{line}" for line in split_lines[1:])
            return formatted

        def _format_location(comment: PRReviewComment) -> str:
            if comment.path:
                if (
                    comment.start_line
                    and comment.end_line
                    and comment.start_line != comment.end_line
                ):
                    line_desc = f"{comment.start_line}-{comment.end_line}"
                elif comment.start_line:
                    line_desc = f"{comment.start_line}"
                else:
                    line_desc = "?"
                return f"{comment.path}:{line_desc}"

            if comment.start_line and comment.end_line:
                if comment.start_line == comment.end_line:
                    return f"Line {comment.start_line}"
                return f"Lines {comment.start_line}-{comment.end_line}"
            if comment.start_line:
                return f"Line {comment.start_line}"
            return "General"

        if rejection_reviews:
            latest = rejection_reviews[-1]
            lines.extend(
                [
                    f"Review Status: {latest.state}",
                    f"Reviewer: {latest.reviewer}",
                    f"Date: {latest.submitted_at}",
                    "",
                ]
            )
            lines.extend(_format_multiline("Review Comment: ", latest.body))
            if latest.body:
                lines.append("")

        if code_comments:
            lines.extend(
                [
                    "-" * 40,
                    "CODE REVIEW COMMENTS:",
                    "-" * 40,
                ]
            )
            for comment in code_comments:
                location = _format_location(comment)
                lines.append(f"Location: {location} (by {comment.reviewer})")
                body_lines = _format_multiline("  ", comment.body)
                lines.extend(body_lines or ["  "])
                lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)
