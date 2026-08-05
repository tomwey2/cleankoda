"""Service layer for user management.

This module contains business logic for managing users,
separating concerns from the route handlers and database operations.
"""

import logging
import uuid

from cleankoda.core.database.models import UserDb
from cleankoda.core.extensions import db

logger = logging.getLogger(__name__)


def get_current_user_id() -> str:
    """Mock implementation to get the current user ID.

    Since a full authentication layer is not yet implemented, this function
    returns the ID of the first user in the database. If no user exists,
    it creates a mock user and returns its ID.

    Returns:
        String representing the user ID.
    """
    first_user = UserDb.query.first()
    if not first_user:
        mock_id = str(uuid.uuid4())
        first_user = UserDb(
            # pyrefly: ignore [unexpected-keyword]
            id=mock_id,
            # pyrefly: ignore [unexpected-keyword]
            first_name="Mock",
            # pyrefly: ignore [unexpected-keyword]
            last_name="User",
        )
        db.session.add(first_user)
        db.session.commit()
        logger.info("Created mock user with ID: %s", mock_id)
        return mock_id

    return first_user.id
