"""
Factory for creating version control system instances.

This module provides a factory function that creates the appropriate version
control system based on the system configuration, enabling easy switching between
different version control systems (GitHub, GitLab, Bitbucket, etc.).
"""

import logging

from src.core.extern.vcs.version_control_system import VersionControlSystem
from src.core.extern.vcs.github_vcs import GitHubVcs
from src.core.database.models import AgentSettingsDb
from src.core.types import VersionControlSystemType

logger = logging.getLogger(__name__)


def create_version_control_system(agent_settings: AgentSettingsDb) -> VersionControlSystem:
    """
    Factory function to create the appropriate version control system.

    The provider type is determined by the 'vcs_type' key inside
    AgentSettings.

    Args:
        agent_settings: Agent settings containing system configuration details

    Returns:
        An instance of an VersionControlSystem implementation

    Raises:
        ValueError: If an unknown provider type is specified

    Example:
        >>> agent_settings = AgentSettingsDb(vcs_type="GITHUB", ...)
        >>> vcs = create_version_control_system(agent_settings)
    """
    vcs_type = agent_settings.vcs_type

    logger.info("Creating version control provider: %s", vcs_type)

    if vcs_type == VersionControlSystemType.GITHUB:
        return GitHubVcs(agent_settings)

    raise ValueError(
        f"Unknown version control provider: {vcs_type}. Supported providers: {VersionControlSystemType.GITHUB}"
    )
