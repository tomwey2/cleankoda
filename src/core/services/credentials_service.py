"""Service layer for credential management.

This module contains business logic for managing user credentials,
separating concerns from the route handlers and database operations.
"""

import logging
from typing import List, Optional

from src.core.extensions import db
from src.core.database.models import UserCredentialDb

logger = logging.getLogger(__name__)


def get_credentials_for_user(user_id: str) -> List[UserCredentialDb]:
    """Retrieve all credentials for a given user.

    Args:
        user_id: The ID of the user.

    Returns:
        List of UserCredential objects.
    """
    return UserCredentialDb.query.filter_by(user_id=user_id).all()


def get_credential_by_id(credential_id: int) -> Optional[UserCredentialDb]:
    """Retrieve a specific credential for a user.

    Args:
        credential_id: The ID of the credential.

    Returns:
        UserCredential or None.
    """
    return UserCredentialDb.query.filter_by(id=credential_id).first()


def save_credential(user_id: str, data: dict) -> UserCredentialDb:
    """Create or update a user credential.

    Args:
        user_id: The ID of the user.
        data: Dictionary containing credential fields.

    Returns:
        The created or updated UserCredential object.
    """
    credential_id = data.get("id")

    if credential_id:
        credential = get_credential_by_id(int(credential_id))
        if not credential:
            raise ValueError(f"Credential {credential_id} not found for user {user_id}")
    else:
        credential = UserCredentialDb(user_id=user_id)
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
    credential = get_credential_by_id(credential_id)
    if not credential:
        return False

    db.session.delete(credential)
    db.session.commit()
    logger.info("Deleted credential ID %s for user %s", credential_id, user_id)
    return True
