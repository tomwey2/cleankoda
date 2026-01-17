"""
Factory for creating board provider instances.

This module provides a factory function that creates the appropriate board
provider based on the system configuration, enabling easy switching between
different board systems (Trello, GitHub, Jira, etc.).
"""

import logging

from agent.integrations.board_provider import BoardProvider

logger = logging.getLogger(__name__)


def create_board_provider(sys_config: dict) -> BoardProvider:
    """
    Factory function to create the appropriate board provider.
    
    The provider type is determined by the 'board_provider' key in sys_config.
    If not specified, defaults to 'trello' for backward compatibility.
    
    Args:
        sys_config: System configuration dictionary containing provider type
                   and provider-specific settings
    
    Returns:
        An instance of a BoardProvider implementation
        
    Raises:
        ValueError: If an unknown provider type is specified
        
    Example:
        >>> sys_config = {"board_provider": "trello", ...}
        >>> provider = create_board_provider(sys_config)
    """
    provider_type = sys_config.get("board_provider", "trello").lower()

    logger.info("Creating board provider: %s", provider_type)

    if provider_type == "trello":
        from agent.integrations.trello_provider import TrelloProvider  # pylint: disable=import-outside-toplevel
        return TrelloProvider(sys_config)

    if provider_type == "github":
        from agent.integrations.github_provider import GitHubProvider  # pylint: disable=import-outside-toplevel,import-error,no-name-in-module
        return GitHubProvider(sys_config)

    if provider_type == "jira":
        from agent.integrations.jira_provider import JiraProvider  # pylint: disable=import-outside-toplevel,import-error,no-name-in-module
        return JiraProvider(sys_config)

    raise ValueError(
        f"Unknown board provider: {provider_type}. "
        f"Supported providers: trello, github, jira"
    )
