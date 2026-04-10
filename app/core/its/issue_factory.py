"""
Factory for creating issue provider instances.

This module provides a factory function that creates the appropriate issue
provider based on the system configuration, enabling easy switching between
different issue systems (Trello, GitHub, Jira, etc.).
"""

import logging

from app.core.its.issue_tracking_system import IssueTrackingSystem
from app.core.its.github_provider import GitHubProvider
from app.core.its.trello_provider import TrelloProvider
from app.core.localdb.models import AgentSettingsDb
from app.core.types import IssueSystemType

logger = logging.getLogger(__name__)


def create_issue_provider(agent_settings: AgentSettingsDb) -> IssueTrackingSystem:
    """
    Factory function to create the appropriate issue provider.

    The provider type is determined by the 'issue_system_type' key inside
    AgentSettings.
    If not specified, defaults to 'trello' for backward compatibility.

    Args:
        agent_settings: Agent settings containing system configuration details

    Returns:
        An instance of an IssueProvider implementation

    Raises:
        ValueError: If an unknown provider type is specified

    Example:
        >>> agent_settings = AgentSettingsDb(its_type="TRELLO", ...)
        >>> provider = create_issue_provider(agent_settings)
    """
    its_type = agent_settings.its_type

    logger.info("Creating issue provider: %s", its_type)

    if its_type == IssueSystemType.TRELLO:
        return TrelloProvider(agent_settings)

    if its_type == IssueSystemType.GITHUB:
        return GitHubProvider(agent_settings)

    raise ValueError(
        f"Unknown issue provider: {its_type}. Supported providers: {IssueSystemType.TRELLO}, {IssueSystemType.GITHUB}"
    )
