"""Pydantic schemas for settings form validation.

These schemas define the structure and validation rules for data flowing
between the web layer (forms) and the service layer.
"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.core.types import IssueTrackingSystemType


class ItsConfigSchema(BaseModel):
    """Schema for Trello configuration form data."""

    its_base_url: Optional[str] = Field(default=None, description="Base URL")
    its_container_id: Optional[str] = Field(default=None, description="Container ID")
    its_parent_id: Optional[str] = Field(default=None, description="Parent ID")
    its_state_backlog: Optional[str] = Field(default=None, description="Backlog state")
    its_state_todo: Optional[str] = Field(default=None, description="Todo state")
    its_state_in_progress: Optional[str] = Field(default=None, description="In-progress state")
    its_state_in_review: Optional[str] = Field(default=None, description="In-review state")
    its_state_done: Optional[str] = Field(default=None, description="Done state")
    its_credential_id: Optional[int] = Field(default=None, description="Credential ID")

    @field_validator("its_container_id", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Optional[str]) -> Optional[str]:
        """Convert empty strings to None."""
        if v == "":
            return None
        return v

    @field_validator("its_credential_id", mode="before")
    @classmethod
    def parse_its_credential_id(cls, v) -> Optional[int]:
        """Parse credential id, defaulting to None on error or empty string."""
        if not v or v == "":
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class LLMConfigSchema(BaseModel):
    """Schema for LLM configuration form data."""

    llm_provider: str = Field(default="mistral", description="LLM provider name")
    llm_model_large: Optional[str] = Field(default=None, description="Large model name")
    llm_model_small: Optional[str] = Field(default=None, description="Small model name")
    llm_temperature: Optional[str] = Field(default=None, description="LLM temperature")

    @field_validator("llm_provider", mode="before")
    @classmethod
    def default_provider(cls, v: Optional[str]) -> str:
        """Default to mistral if empty."""
        if not v or v == "":
            return "mistral"
        return v

    @field_validator("llm_model_large", "llm_model_small", "llm_temperature", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Optional[str]) -> Optional[str]:
        """Convert empty strings to None."""
        if v == "":
            return None
        return v


class SettingsFormSchema(BaseModel):
    """Schema for the complete settings form submission."""

    its_type: str = Field(default=IssueTrackingSystemType.TRELLO, description="Its type")
    polling_interval_seconds: int = Field(
        default=60, ge=10, le=3600, description="Polling interval in seconds"
    )
    is_active: bool = Field(default=False, description="Whether agent is active")
    agent_skill_level: Optional[str] = Field(default=None, description="Agent skill level")
    agent_gender: Optional[str] = Field(default=None, description="Agent gender")
    repo_type: str = Field(default="GITHUB", description="Repository type")
    repo_url: Optional[str] = Field(default=None, description="GitHub repository URL")

    its_config: ItsConfigSchema = Field(
        default_factory=ItsConfigSchema, description="Issue tracking system configuration"
    )
    llm_config: LLMConfigSchema = Field(
        default_factory=LLMConfigSchema, description="LLM configuration"
    )

    @field_validator("its_type", mode="before")
    @classmethod
    def default_issue_system(cls, v: Optional[str]) -> str:
        """Default to TRELLO if empty."""
        if not v or v == "":
            return IssueTrackingSystemType.TRELLO
        return v

    @field_validator("polling_interval_seconds", mode="before")
    @classmethod
    def parse_polling_interval(cls, v) -> int:
        """Parse polling interval, defaulting to 60 on error."""
        if v is None or v == "":
            return 60
        try:
            return int(v)
        except (ValueError, TypeError):
            return 60

    @field_validator("is_active", mode="before")
    @classmethod
    def parse_is_active(cls, v) -> bool:
        """Parse is_active from form checkbox."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "on", "yes")
        return bool(v)
