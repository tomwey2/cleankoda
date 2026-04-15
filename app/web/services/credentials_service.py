"""Service layer for credential management.

This module contains business logic for managing user credentials,
separating concerns from the route handlers and database operations.
"""

import logging
from typing import List, Optional
import uuid

from app.core.extensions import db
from app.core.localdb.models import User, UserCredential

logger = logging.getLogger(__name__)


def get_current_user_id() -> str:
    """Mock implementation to get the current user ID.
    
    Since a full authentication layer is not yet implemented, this function
    returns the ID of the first user in the database. If no user exists,
    it creates a mock user and returns its ID.

    Returns:
        String representing the user ID.
    """
    first_user = User.query.first()
    if not first_user:
        mock_id = str(uuid.uuid4())
        first_user = User(
            id=mock_id,
            first_name="Mock",
            last_name="User"
        )
        db.session.add(first_user)
        db.session.commit()
        logger.info("Created mock user with ID: %s", mock_id)
        return mock_id
        
    return first_user.id


def get_credentials_for_user(user_id: str) -> List[UserCredential]:
    """Retrieve all credentials for a given user.

    Args:
        user_id: The ID of the user.

    Returns:
        List of UserCredential objects.
    """
    return UserCredential.query.filter_by(user_id=user_id).all()


def get_credential_by_id(user_id: str, credential_id: int) -> Optional[UserCredential]:
    """Retrieve a specific credential for a user.

    Args:
        user_id: The ID of the user.
        credential_id: The ID of the credential.

    Returns:
        UserCredential or None.
    """
    return UserCredential.query.filter_by(user_id=user_id, id=credential_id).first()


def save_credential(user_id: str, data: dict) -> UserCredential:
    """Create or update a user credential.

    Args:
        user_id: The ID of the user.
        data: Dictionary containing credential fields.
        
    Returns:
        The created or updated UserCredential object.
    """
    credential_id = data.get("id")
    
    if credential_id:
        credential = get_credential_by_id(user_id, int(credential_id))
        if not credential:
            raise ValueError(f"Credential {credential_id} not found for user {user_id}")
    else:
        credential = UserCredential(user_id=user_id)
        db.session.add(credential)

    # Map fields
    if "credential_type" in data:
        credential.credential_type = data["credential_type"]
    if "name" in data:
        credential.name = data["name"]
    if "username_or_email" in data:
        credential.username_or_email = data["username_or_email"]
        
    # Encrypted fields
    if "password" in data and data["password"]:
        credential.password = data["password"]
    if "api_key" in data and data["api_key"]:
        credential.api_key = data["api_key"]
    if "api_token" in data and data["api_token"]:
        credential.api_token = data["api_token"]

    db.session.commit()
    logger.info("Saved credential ID %s for user %s", credential.id, user_id)
    return credential


def delete_credential(user_id: str, credential_id: int) -> bool:
    """Delete a specific credential for a user.

    Args:
        user_id: The ID of the user.
        credential_id: The ID of the credential.

    Returns:
        True if deleted, False if not found.
    """
    credential = get_credential_by_id(user_id, credential_id)
    if not credential:
        return False
        
    db.session.delete(credential)
    db.session.commit()
    logger.info("Deleted credential ID %s for user %s", credential_id, user_id)
    return True
