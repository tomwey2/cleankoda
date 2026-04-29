"""Service layer for settings management.

This module contains business logic for managing agent configuration settings,
separating concerns from the route handlers and database operations.
"""

import logging

from src.core.database.models import AgentSettingsDb

logger = logging.getLogger(__name__)


def get_or_create_agent_settings(user_id: str) -> AgentSettingsDb:
    """Retrieve existing settings or create a new one with defaults.

    Returns:
        AgentSettings instance (may be transient if newly created).
    """
    settings = AgentSettingsDb.query.filter_by(user_id=user_id).first()
    if not settings:
        settings = AgentSettingsDb(user_id=user_id)
    return settings
