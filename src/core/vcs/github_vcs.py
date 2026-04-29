"""
GitHub implementation of the VersionControlSystem interface.

This module provides a GitHub VCS class that wraps the GitHub API client and implements
the VersionControlSystem interface for consistent version control operations across different systems.
"""

from src.core.database.models import AgentSettingsDb
from src.core.vcs.version_control_system import VersionControlSystem, PullRequest


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
        pass

    async def add_comment_to_pr(self, pr_number: int, comment: str) -> None:
        pass
