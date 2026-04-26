"""
Factory for creating issue provider instances.

This module provides a factory function that creates the appropriate issue
provider based on the system configuration, enabling easy switching between
different issue systems (Trello, GitHub, Jira, etc.).
"""

import logging

from src.core.its.issue_tracking_system import IssueTrackingSystem
from src.core.its.github_its import GitHubIts
from src.core.its.trello_its import TrelloIts
from src.core.database.models import AgentSettingsDb
from src.core.types import IssueTrackingSystemType

logger = logging.getLogger(__name__)


def create_issue_tracking_system(agent_settings: AgentSettingsDb) -> IssueTrackingSystem:
    """
    Factory function to create the appropriate issue provider.

    The provider type is determined by the 'its_type' key inside
    AgentSettings.
    If not specified, defaults to 'trello' for backward compatibility.

    Args:
        agent_settings: Agent settings containing system configuration details

    Returns:
        An instance of an IssueTrackingSystem implementation

    Raises:
        ValueError: If an unknown provider type is specified

    Example:
        >>> agent_settings = AgentSettingsDb(its_type="TRELLO", ...)
        >>> provider = create_issue_provider(agent_settings)
    """
    its_type = agent_settings.its_type

    logger.info("Creating issue provider: %s", its_type)

    if its_type == IssueTrackingSystemType.TRELLO:
        return TrelloIts(agent_settings)

    if its_type == IssueTrackingSystemType.GITHUB:
        return GitHubIts(agent_settings)

    raise ValueError(
        f"Unknown issue provider: {its_type}. Supported providers: {IssueTrackingSystemType.TRELLO}, {IssueTrackingSystemType.GITHUB}"
    )
