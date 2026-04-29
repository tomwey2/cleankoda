"""Service layer for user management.

This module contains business logic for managing users,
separating concerns from the route handlers and database operations.
"""

import logging
import uuid

from src.core.extensions import db
from src.core.database.models import UserDb

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
        first_user = UserDb(id=mock_id, first_name="Mock", last_name="User")
        db.session.add(first_user)
        db.session.commit()
        logger.info("Created mock user with ID: %s", mock_id)
        return mock_id

    return first_user.id
