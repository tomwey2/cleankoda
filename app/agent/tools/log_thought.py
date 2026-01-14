"""Tool for logging agent thoughts without affecting state."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.tools._base import logger


@tool
def log_thought(thought: str):
    """Log an internal thought to aid reasoning without changing state."""
    logger.debug("🤔 AGENT THOUGHT: %s", thought)
    return "Thought recorded. Proceed with the next tool."
