"""Defines the SQLAlchemy database models for the application.

This module contains the class definitions for all database models used by
SQLAlchemy. Each class corresponds to a table in the database.
"""

from typing import Any, Dict

from sqlalchemy import ForeignKey

from app.core.extensions import db
from app.core.security import EncryptedString

# pylint: disable=too-few-public-methods
DEFAULT_TRELLO_BASE_URL = "https://api.trello.com/1"


class AgentSettings(db.Model):
    """Represents the configuration for the AI agent.

    This model stores settings required for the agent to operate, including
    connections to issue tracking systems (like Trello), version control
    repositories (like GitHub), and its own operational parameters like
    polling frequency.
    """

    __tablename__ = "agent_settings"

    id = db.Column(db.Integer, primary_key=True)
    # Generic Issue System Fields
    issue_system_type = db.Column(
        "task_system_type", db.String(50), nullable=False, default="TRELLO"
    )  # e.g., "TRELLO", "JIRA", "CUSTOM"

    issue_backlog_state = db.Column("task_backlog_state", db.String(100), nullable=True)
    issue_readfrom_state = db.Column("task_readfrom_state", db.String(100), nullable=True)
    issue_in_progress_state = db.Column("task_in_progress_state", db.String(100), nullable=True)
    issue_moveto_state = db.Column("task_moveto_state", db.String(100), nullable=True)
    llm_provider = db.Column(db.String(50), nullable=True)
    llm_model_large = db.Column(db.String(100), nullable=True)
    llm_model_small = db.Column(db.String(100), nullable=True)
    llm_temperature = db.Column(db.String(16), nullable=True)

    # Existing Fields
    repo_type = db.Column(
        db.String(50), nullable=False, default="GITHUB"
    )  # e.g., "GITHUB", "BITBUCKET"
    github_repo_url = db.Column(db.String(200))
    polling_interval_seconds = db.Column(db.Integer, nullable=False, default=60)
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    agent_skill_level = db.Column(db.String(50), nullable=True)
    issue_systems = db.relationship(
        "IssueSystem",
        back_populates="agent_settings",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def get_issue_system(self, provider: str) -> "IssueSystem | None":
        """Get IssueSystem by provider name."""
        if self.issue_systems and isinstance(self.issue_systems, list):
            for ts in self.issue_systems:
                if ts.issue_provider == provider:
                    return ts
        return None

    def get_active_issue_system(self) -> "IssueSystem | None":
        """Get the currently active IssueSystem based on issue_system_type."""
        provider = (
            "trello" if self.issue_system_type == "TRELLO" else self.issue_system_type.lower()
        )
        return self.get_issue_system(provider)

    def __repr__(self):
        return f"<AgentSettings {self.id} type={self.issue_system_type}>"

    def as_dict(self) -> Dict[str, Any]:
        """Return a plain dictionary of column values for logging/debugging."""
        return {
            key: getattr(self, key)
            for key in self.__mapper__.columns.keys()  # type: ignore[attr-defined]
        }


class IssueSystem(db.Model):
    """Represents an external issue system configuration (e.g., Trello, GitHub Projects)."""

    __tablename__ = "task_system"

    id = db.Column(db.Integer, primary_key=True)
    agent_settings_id = db.Column(
        db.Integer,
        ForeignKey("agent_settings.id"),
        nullable=False,
        index=True,
    )
    issue_system_type = db.Column(
        "task_system_type", db.String(50), nullable=False, default="TRELLO"
    )
    issue_provider = db.Column("task_provider", db.String(50), nullable=False)
    api_key = db.Column(EncryptedString, nullable=True)
    token = db.Column(EncryptedString, nullable=True)
    base_url = db.Column(db.String(200), nullable=True)
    board_id = db.Column(db.String(100), nullable=True)
    # GitHub Projects specific fields
    project_owner = db.Column(db.String(100), nullable=True)
    project_number = db.Column(db.Integer, nullable=True)
    # State mappings per provider
    state_backlog = db.Column(db.String(100), nullable=True)
    state_todo = db.Column(db.String(100), nullable=True)
    state_in_progress = db.Column(db.String(100), nullable=True)
    state_in_review = db.Column(db.String(100), nullable=True)

    agent_settings = db.relationship(
        "AgentSettings",
        back_populates="issue_systems",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "agent_settings_id", "task_provider", name="uq_agent_settings_provider"
        ),
    )

    def __repr__(self):
        return f"<IssueSystem {self.id} provider={self.issue_provider}>"


# pylint: disable=too-few-public-methods
class AgentIssue(db.Model):
    """Model for tracking issues"""

    __tablename__ = "agent_tasks"

    id = db.Column(db.Integer, primary_key=True)

    # Issue ID from the external issue system
    issue_id = db.Column("task_id", db.String(64), nullable=False, unique=True, index=True)
    # Issue title from the external issue system
    issue_name = db.Column("task_name", db.String(500), nullable=False)
    # Issue description from the external issue system
    issue_description = db.Column("task_description", db.Text, nullable=True)

    # Issue type (e.g., "coding", "analyzing", "bugfixing")
    issue_type = db.Column("task_type", db.String(20), nullable=True)
    # Issue skill level ("junior", "senior")
    issue_skill_level = db.Column("task_skill_level", db.String(20), nullable=True)
    # The LLM description of the skill level decision
    issue_skill_level_reasoning = db.Column("task_skill_level_reasoning", db.Text, nullable=True)

    # Branch name of the repository
    repo_branch_name = db.Column("branch_name", db.String(200), nullable=True)
    # URL of the repository
    repo_url = db.Column(db.String(200), nullable=True)
    # Number of the Pull Request in GitHub
    repo_pr_number = db.Column("pr_number", db.Integer, nullable=True)
    # URL of the Pull Request
    repo_pr_url = db.Column("pr_url", db.String(500), nullable=True)

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
        "AgentAction",
        backref="issue",
        cascade="all, delete-orphan",  # <-- That is important for SQLAlchemy!
        passive_deletes=True,  # <-- That is important for SQLAlchemy!
    )

    def __repr__(self):
        return f"<Issue id={self.issue_id} branch={self.branch_name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "issue_name": self.issue_name,
            "issue_description": self.issue_description,
            "issue_type": self.issue_type,
            "issue_skill_level": self.issue_skill_level,
            "issue_skill_level_reasoning": self.issue_skill_level_reasoning,
            "repo_branch_name": self.repo_branch_name,
            "repo_url": self.repo_url,
            "repo_pr_number": self.repo_pr_number,
            "repo_pr_url": self.repo_pr_url,
            "plan_content": self.plan_content,
            "plan_state": self.plan_state,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# pylint: disable=too-few-public-methods
class AgentAction(db.Model):
    """Model for tracking agent actions"""

    __tablename__ = "agent_actions"

    id = db.Column(db.Integer, primary_key=True)
    # Foreign key to Issue
    issue_id = db.Column(
        "task_id", db.Integer, db.ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=True
    )
    # Current node of the agent ("issue_fetch", "coder", "tester", "issue_update")
    current_node = db.Column(db.String(50), nullable=True)
    # Tool used by the agent
    tool_name = db.Column(db.String(50), nullable=True)
    tool_arg0_name = db.Column(db.String(50), nullable=True)
    tool_arg0_value = db.Column(db.String(200), nullable=True)

    # created_at and updated_at are automatically managed by SQLAlchemy
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f"<AgentAction id={self.id} issue_id={self.issue_id} node={self.current_node}>"

    def to_dict(self):
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "current_node": self.current_node,
            "tool_name": self.tool_name,
            "tool_arg0_name": self.tool_arg0_name,
            "tool_arg0_value": self.tool_arg0_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
