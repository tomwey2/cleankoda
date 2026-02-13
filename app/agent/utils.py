"""Environment helpers for locating the workspace and workbench."""

from __future__ import annotations

from typing import Final

from app.core.config import get_env_settings

__all__ = [
    "get_workbench",
    "get_workspace",
    "get_codespace",
]


DEFAULT_WORKSPACE: Final[str] = "/coding-agent-workspace"


def get_workspace() -> str:
    """Return the workspace directory path."""
    return get_env_settings().workspace


def get_workbench() -> str:
    """Return the workbench container name."""
    return get_env_settings().workbench


def get_codespace() -> str:
    """Return the path to the code repository."""
    return f"{get_workspace()}/code"
