"""Defines the SQLAlchemy database models for the application.

This module contains the class definitions for all database models used by
SQLAlchemy. Each class corresponds to a table in the database.
"""

from typing import Any, Dict

from app.core.extensions import db
from app.core.security import EncryptedString
from app.core.types import IssueTrackingSystemType

# pylint: disable=too-few-public-methods
DEFAULT_TRELLO_BASE_URL = "https://api.trello.com/1"


class AgentSettingsDb(db.Model):
    """Represents the configuration for the AI agent.

    This model stores settings required for the agent to operate, including
    connections to issue tracking systems (like Trello), version control
    repositories (like GitHub), and its own operational parameters like polling frequency.
    """

    __tablename__ = "agent_settings"

    id = db.Column(db.Integer, primary_key=True)

    # Common settings
    polling_interval_seconds = db.Column(db.Integer, nullable=False, default=60)
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    agent_skill_level = db.Column(db.String(20), nullable=True)
    agent_gender = db.Column(db.String(20), nullable=True)

    # Issue tracking system: e.g., "TRELLO", "JIRA", "GITHUB ISSUES"
    its_type = db.Column(db.String(50), nullable=False, default=IssueTrackingSystemType.TRELLO)
    its_api_key = db.Column(EncryptedString, nullable=True)
    its_token = db.Column(EncryptedString, nullable=True)
    its_base_url = db.Column(db.String(200), nullable=True)
    its_container_id = db.Column(db.String(100), nullable=True)
    its_parent_id = db.Column(db.String(100), nullable=True)
    its_state_backlog = db.Column(db.String(50), nullable=True)
    its_state_todo = db.Column(db.String(50), nullable=True)
    its_state_in_progress = db.Column(db.String(50), nullable=True)
    its_state_in_review = db.Column(db.String(50), nullable=True)
    its_state_done = db.Column(db.String(50), nullable=True)

    # Repo system: e.g., "GITHUB", "BITBUCKET"
    repo_type = db.Column(db.String(50), nullable=False, default="GITHUB")
    repo_url = db.Column(db.String(200))

    # LLM system: e.g., "OPENAI", "ANTHROPIC", "GOOGLE"
    llm_provider = db.Column(db.String(50), nullable=False)
    llm_model_large = db.Column(db.String(100), nullable=True)
    llm_model_small = db.Column(db.String(100), nullable=True)
    llm_temperature = db.Column(db.String(16), nullable=True)

    # created_at and updated_at are automatically managed by SQLAlchemy
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f"<AgentSettings {self.id} type={self.its_type}>"

    def as_dict(self) -> Dict[str, Any]:
        """Return a plain dictionary of column values for logging/debugging."""
        return {
            key: getattr(self, key)
            for key in self.__mapper__.columns.keys()  # type: ignore[attr-defined]
        }


# pylint: disable=too-few-public-methods
class AgentStatesDb(db.Model):
    """Model for persistence agent states"""

    __tablename__ = "agent_states"

    id = db.Column(db.Integer, primary_key=True)

    # Issue ID from the external issue system
    issue_id = db.Column(db.String(100), nullable=False, unique=True, index=True)
    # Issue title from the external issue system
    issue_name = db.Column(db.String(500), nullable=False)
    # Issue description from the external issue system
    issue_description = db.Column(db.Text, nullable=True)

    # Issue state from the external issue system converted to IssueStateType
    issue_state = db.Column(db.String(20), nullable=True)
    # link to the issue in the issue tracking system
    issue_url = db.Column(db.String(200), nullable=True)
    # Issue type (e.g., "coding", "analyzing", "bugfixing")
    issue_type = db.Column(db.String(20), nullable=True)
    # Issue skill level ("junior", "senior")
    issue_skill_level = db.Column(db.String(20), nullable=True)
    # The LLM description of the skill level decision
    issue_skill_level_reasoning = db.Column(db.Text, nullable=True)
    issue_is_active = db.Column(db.Boolean, nullable=False, default=False)

    # Branch name of the repository
    repo_branch_name = db.Column(db.String(100), nullable=True)
    # Number of the Pull Request in GitHub
    repo_pr_number = db.Column(db.Integer, nullable=True)
    # URL of the Pull Request
    repo_pr_url = db.Column(db.String(200), nullable=True)

    # Content of the implementation plan
    plan_content = db.Column(db.Text, nullable=True)
    # State of the implementation plan ("created", "updated", "approved", "rejected")
    plan_state = db.Column(db.String(20), nullable=True)
    # Working state of the issue ("working...", "finished")
    working_state = db.Column(db.String(20), nullable=True)
    # User message
    user_message = db.Column(db.String(200), nullable=True)

    # created_at and updated_at are automatically managed by SQLAlchemy
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    actions = db.relationship(
        "AgentActionDb",
        backref="state",
        cascade="all, delete-orphan",  # <-- That is important for SQLAlchemy!
        passive_deletes=True,  # <-- That is important for SQLAlchemy!
    )

    def __repr__(self):
        return f"<Issue id={self.issue_id} branch={self.branch_name}>"

    def as_dict(self) -> Dict[str, Any]:
        """Return a plain dictionary of column values for logging/debugging."""
        return {
            key: getattr(self, key)
            for key in self.__mapper__.columns.keys()  # type: ignore[attr-defined]
        }


# pylint: disable=too-few-public-methods
class AgentActionDb(db.Model):
    """Model for tracking agent actions"""

    __tablename__ = "agent_actions"

    id = db.Column(db.Integer, primary_key=True)
    # Foreign key to Issue
    state_id = db.Column(
        db.Integer, db.ForeignKey("agent_states.id", ondelete="CASCADE"), nullable=True
    )
    # Current node of the agent ("issue_fetch", "coder", "tester", "issue_update")
    node_name = db.Column(db.String(50), nullable=True)
    # Tool used by the agent
    tool_name = db.Column(db.String(50), nullable=True)
    tool_arg0_name = db.Column(db.String(50), nullable=True)
    tool_arg0_value = db.Column(db.String(200), nullable=True)

    # created_at and updated_at are automatically managed by SQLAlchemy
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f"<AgentActionDb id={self.id} state_id={self.state_id} node={self.current_node}>"

    def as_dict(self) -> Dict[str, Any]:
        """Return a plain dictionary of column values for logging/debugging."""
        return {
            key: getattr(self, key)
            for key in self.__mapper__.columns.keys()  # type: ignore[attr-defined]
        }
