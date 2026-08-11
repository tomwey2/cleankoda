"""Flask application configuration.

This module defines the configuration variables for the Flask application.
It uses Pydantic Settings for centralized environment variable access.
"""

import logging
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Accumulates all environment variables used in the application.

    Attributes:
        encryption_key: Fernet encryption key for database encryption (required).
        workspace: Path to the agent's coding workspace (required).
        deployment_mode: Deployment mode (ON_PREMISE or SERVERLESS) (required).
        secret_key: Flask secret key for session management.
        database_url: Database connection URL (optional).
        instance_dir: Directory for sqlite database files and other instance data.
        workbench: Docker container name for the workbench.
        workbench_workspace: Path to workspace inside the workbench container.
        agent_stack: Preferred agent stack override.
        enable_mcp_servers: Whether to enable MCP servers.
        llm_calls_per_second: LLM calls per second limit.
    """

    # Required settings (needed for app startup)
    encryption_key: str
    workspace: str
    deployment_mode: str

    # Configuration with defaults
    secret_key: str = "a-default-secret-key-for-development"
    database_url: str | None = None
    instance_dir: str = "/coding-agent/app/instance"
    workbench: str = "workbench-backend"
    workbench_workspace: str | None = None
    agent_stack: str = ""
    enable_mcp_servers: bool = True
    llm_calls_per_second: float = 0.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignores additional variables in the .env file
    )

    @model_validator(mode="after")
    def set_defaults(self) -> "Settings":
        """Post-initialization defaults."""
        if not self.workbench_workspace:
            self.workbench_workspace = self.workspace
        return self

    def get_database_uri(self, base_dir: Path) -> str:
        """Get the database URI, computing default if not set."""
        if self.database_url:
            return self.database_url

        db_dir = Path(self.instance_dir) if self.instance_dir else base_dir / "instance"
        db_dir = db_dir.resolve()
        return f"sqlite:///{db_dir / 'agent.db'}"

    def require_encryption_key(self) -> str:
        """Get encryption key or raise if not configured."""
        if not self.encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY is required. Set the ENCRYPTION_KEY environment variable."
            )
        return self.encryption_key

    def log_settings(self) -> None:
        """Log loaded environment settings."""
        logger.info("MCP enabled: %s", self.enable_mcp_servers)
        logger.info("INSTANCE_DIR: %s", self.instance_dir or "Not set")
        logger.info("WORKBENCH: %s", self.workbench or "Not set")
        logger.info("WORKSPACE: %s", self.workspace)
        logger.info("AGENT_STACK: %s", self.agent_stack or "Not set")
        logger.info("LLM_CALLS_PER_SECOND: %s", self.llm_calls_per_second)


# Instantiation of the settings, which can be imported throughout the project
settings = Settings()

# Database configuration
BASE_DIR = Path(__file__).resolve().parent.parent

SQLALCHEMY_TRACK_MODIFICATIONS = False
SCHEDULER_API_ENABLED = True
