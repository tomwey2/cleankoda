"""Shared helpers for individual tool modules."""

from __future__ import annotations

import logging

import docker
from docker.errors import APIError, NotFound

from agent.utils import get_workbench, get_workspace

logger = logging.getLogger(__name__)

try:  # docker socket might be unavailable in some environments
    DOCKER_CLIENT = docker.from_env()
except Exception as exc:  # pylint: disable=broad-exception-caught
    logger.warning("No docker connection! %s", exc)
    DOCKER_CLIENT = None

MAX_TOOL_OUTPUT_CHARS = 20000


def truncate_tool_output(output: str, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """Truncate long command output while keeping the start and end."""
    if len(output) <= limit:
        return output

    half = limit // 2
    return (
        output[:half]
        + "\n... [output truncated to stay within prompt budget] ...\n"
        + output[-half:]
    )


__all__ = [
    "logger",
    "DOCKER_CLIENT",
    "APIError",
    "NotFound",
    "get_workbench",
    "get_workspace",
    "truncate_tool_output",
    "MAX_TOOL_OUTPUT_CHARS",
]
