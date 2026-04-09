"""
Factory for creating issue provider instances.

This module provides a factory function that creates the appropriate issue
provider based on the system configuration, enabling easy switching between
different issue systems (Trello, GitHub, Jira, etc.).
"""

import logging

from app.core.issueprovider.issue_provider import IssueProvider
from app.core.issueprovider.github_provider import GitHubProvider
from app.core.issueprovider.trello_provider import TrelloProvider
from app.core.localdb.models import AgentSettings

logger = logging.getLogger(__name__)


def create_issue_provider(agent_settings: AgentSettings) -> IssueProvider:
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
        >>> agent_settings = AgentSettings(issue_system_type="TRELLO", ...)
        >>> provider = create_issue_provider(agent_settings)
    """
    provider_type = agent_settings.issue_system_type.lower()

    logger.info("Creating issue provider: %s", provider_type)

    if provider_type == "trello":
        return TrelloProvider(agent_settings)

    if provider_type == "github":
        return GitHubProvider(agent_settings)

    raise ValueError(f"Unknown issue provider: {provider_type}. Supported providers: trello, github")
