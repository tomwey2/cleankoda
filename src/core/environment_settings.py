"""Centralized environment settings for the application.

This module provides a single dataclass that accumulates all environment
variables used throughout the application. All other modules should import
from here instead of accessing os.environ directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EnvironmentSettings:  # pylint: disable=too-many-instance-attributes
    """Accumulates all environment variables used in the application.

    This dataclass centralizes environment variable access, making the code
    more testable and easier to reason about. Use the from_env() factory
    method to create an instance from the current environment.

    Most settings are optional and validated at use time via helper methods
    and features that don't need certain credentials to run without them.

    Attributes:
        encryption_key: Fernet encryption key for database encryption (required).
        workspace: Path to the agent's coding workspace (required). This is where
            the agent operates and may be a host path when running locally.
        secret_key: Flask secret key for session management.
        database_url: Database connection URL (optional, uses sqlite default).
        instance_dir: Directory for sqlite database files and other instance data.
        workbench: Docker container name for the workbench.
        workbench_workspace: Path to workspace inside the workbench container. This
            is where commands are executed and defaults to the workspace value.
        agent_stack: Preferred agent stack (backend/frontend) override.
        enable_mcp_servers: Whether to enable MCP servers.
        llm_calls_per_second: LLM calls per second.
        deployment_mode: Deployment mode (ON_PREMISE or SERVERLESS).
    """

    # Required settings (needed for app startup)
    encryption_key: str
    workspace: str
    deployment_mode: str

    # Configuration with defaults
    secret_key: str = "a-default-secret-key-for-development"
    database_url: str | None = None
    instance_dir: str = "/coding-agent/app/instance"
    workbench: str = ""
    workbench_workspace: str = ""
    agent_stack: str = ""
    enable_mcp_servers: bool = True
    llm_calls_per_second: float = 0.0

    @classmethod
    def from_env(cls) -> EnvironmentSettings:
        """Create EnvironmentSettings from the current environment.

        Only ENCRYPTION_KEY and WORKSPACE are required at initialization.
        Other settings like GITHUB_TOKEN are optional and validated when used.

        Raises:
            ValueError: If required environment variables (ENCRYPTION_KEY, WORKSPACE) are missing.

        Returns:
            EnvironmentSettings instance populated from os.environ.
        """
        # Required variables - raise if missing
        encryption_key = os.environ.get("ENCRYPTION_KEY")
        if not encryption_key:
            raise ValueError("ENCRYPTION_KEY is not set. Application cannot start.")

        workspace = os.environ.get("WORKSPACE")
        if not workspace:
            raise ValueError("WORKSPACE is not set.")

        deployment_mode = os.environ.get("DEPLOYMENT_MODE")
        if deployment_mode not in ["ON_PREMISE", "SERVERLESS"]:
            raise ValueError("DEPLOYMENT_MODE is not set.")

        # Parse ENABLE_MCP_SERVERS boolean
        enable_mcp_str = os.environ.get("ENABLE_MCP_SERVERS", "true").lower()
        enable_mcp_servers = enable_mcp_str in {"true", "1", "yes", "on"}

        llm_calls_per_second = float(os.environ.get("LLM_CALLS_PER_SECOND", "0"))

        # WORKBENCH_WORKSPACE defaults to WORKSPACE if not set
        workbench_workspace = os.environ.get("WORKBENCH_WORKSPACE", workspace)

        return cls(
            encryption_key=encryption_key,
            workspace=workspace,
            workbench_workspace=workbench_workspace,
            secret_key=os.environ.get("SECRET_KEY", "a-default-secret-key-for-development"),
            database_url=os.environ.get("DATABASE_URL"),
            instance_dir=os.environ.get("INSTANCE_DIR", "/coding-agent/app/instance"),
            workbench=os.environ.get("WORKBENCH", "workbench-backend"),
            agent_stack=os.environ.get("AGENT_STACK", ""),
            enable_mcp_servers=enable_mcp_servers,
            llm_calls_per_second=llm_calls_per_second,
            deployment_mode=deployment_mode,
        )

    def get_database_uri(self, base_dir: Path) -> str:
        """Get the database URI, computing default if not set.

        Args:
            base_dir: Base directory for computing default sqlite path.

        Returns:
            Database connection URI string.
        """
        if self.database_url:
            return self.database_url

        db_dir = Path(self.instance_dir) if self.instance_dir else base_dir / "instance"
        db_dir = db_dir.resolve()
        return f"sqlite:///{db_dir / 'agent.db'}"

    def require_encryption_key(self) -> str:
        """Get encryption key or raise if not configured.

        Returns:
            Encryption key string.

        Raises:
            ValueError: If ENCRYPTION_KEY is not set.
        """
        if not self.encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY is required. Set the ENCRYPTION_KEY environment variable."
            )
        return self.encryption_key
