"""Defines the SQLAlchemy database models for the application.

This module contains the class definitions for all database models used by
SQLAlchemy. Each class corresponds to a table in the database.
"""

import os

from cryptography.fernet import Fernet
from sqlalchemy import LargeBinary, TypeDecorator

from app.core.extensions import db

key = os.environ.get("ENCRYPTION_KEY")
if not key:
    raise ValueError("ENCRYPTION_KEY is not set. Application cannot start.")
encryption_key = Fernet(key.encode())


# pylint: disable=too-many-ancestors
class EncryptedString(TypeDecorator):
    """Encrypts data on its way into the database, decrypts it on its way out."""

    impl = LargeBinary  # Stored as Binary/Blob in the DB
    cache_ok = True

    @property
    def python_type(self):
        return str

    def process_bind_param(self, value, dialect):
        """Encrypt before saving"""
        if value is not None:
            # Must be bytes for Fernet
            value_bytes = value.encode("utf-8")
            encrypted_value = encryption_key.encrypt(value_bytes)
            return encrypted_value
        return value

    def process_result_value(self, value, dialect):
        """Decrypt after loading"""
        if value is not None:
            decrypted_value = encryption_key.decrypt(value)
            return decrypted_value.decode("utf-8")
        return value

    def process_literal_param(self, value, dialect):
        """Handles rendering of a literal parameter for this type.

        This is used for features like literal_binds.
        """
        processed_value = self.process_bind_param(value, dialect)
        if processed_value is None:
            return "NULL"

        return dialect.type_descriptor(self.impl).process_literal_param(  # type: ignore[attr-defined] # pylint: disable=line-too-long
            processed_value, dialect
        )


# pylint: disable=too-few-public-methods
class AgentConfig(db.Model):
    """Represents the configuration for the AI agent.

    This model stores settings required for the agent to operate, including
    connections to task management systems (like Trello), version control
    repositories (like GitHub), and its own operational parameters like
    polling frequency.
    """

    __tablename__ = "agent_config"

    id = db.Column(db.Integer, primary_key=True)
    # Generic Task System Fields
    task_system_type = db.Column(
        db.String(50), nullable=False, default="TRELLO"
    )  # e.g., "TRELLO", "JIRA", "CUSTOM"
    system_config_json = db.Column(
        db.Text, nullable=True
    )  # JSON blob for credentials, IDs, etc.

    # Existing Fields
    repo_type = db.Column(
        db.String(50), nullable=False, default="GITHUB"
    )  # e.g., "GITHUB", "BITBUCKET"
    github_repo_url = db.Column(
        db.String(200),
        default="https://github.com/tomwey2/calculator-spring-docker-jenkins.git",
    )
    polling_interval_seconds = db.Column(db.Integer, nullable=False, default=60)
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    agent_skill_level = db.Column(db.String(50), nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<AgentConfig {self.id}>"


# pylint: disable=too-few-public-methods
class Task(db.Model):
    """Model for tracking tasks"""

    __tablename__ = "task"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    task_name = db.Column(db.String(500), nullable=False)
    branch_name = db.Column(db.String(200), nullable=False)
    repo_url = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<Task id={self.task_id} branch={self.branch_name}>"
