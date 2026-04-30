"""
GitHub implementation of the VersionControlSystem interface.

This module provides a GitHub VCS class that wraps the GitHub API client and implements
the VersionControlSystem interface for consistent version control operations across different systems.
"""

import httpx

from src.core.database.models import AgentSettingsDb
from src.core.vcs.version_control_system import VersionControlSystem, PullRequest
from src.core.services.credentials_service import get_repo_token


class GitHubVcs(VersionControlSystem):
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

    def get_default_branch_name(self) -> str:
        return self.agent_settings.vcs_default_branch

    async def create_pull_request(self, title: str, source_branch: str) -> PullRequest:
        token = get_repo_token(self.agent_settings.vcs_credential_id)
        if not token:
            raise ValueError("GitHub token not configured for VCS.")

        base_url = self.agent_settings.vcs_api_base_url or "https://api.github.com"
        base_url = base_url.rstrip("/")
        repo_id = self.agent_settings.vcs_project_identifier
        if not repo_id:
            raise ValueError("GitHub repository identifier not configured.")

        url = f"{base_url}/repos/{repo_id}/pulls"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        payload = {
            "title": title,
            "head": source_branch,
            "base": self.get_default_branch_name(),
            "body": "Pull request created by CleanKoda agent."
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)

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

    async def add_comment_to_pr(self, pr_number: int, comment: str) -> None:
        token = get_repo_token(self.agent_settings.vcs_credential_id)
        if not token:
            raise ValueError("GitHub token not configured for VCS.")

        base_url = self.agent_settings.vcs_api_base_url or "https://api.github.com"
        base_url = base_url.rstrip("/")
        repo_id = self.agent_settings.vcs_project_identifier
        if not repo_id:
            raise ValueError("GitHub repository identifier not configured.")

        # In GitHub API, PR comments are created via the issues endpoint
        url = f"{base_url}/repos/{repo_id}/issues/{pr_number}/comments"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        
        payload = {
            "body": comment
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)

        if response.status_code != 201:
            raise RuntimeError(f"Failed to add comment to pull request: {response.text}")
