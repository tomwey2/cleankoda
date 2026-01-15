"""Tool for logging agent thoughts without affecting state."""

import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def thinking(thought: str):
    """Log an internal thought to aid reasoning without changing state."""
    logger.debug("🤔 Thinking: %s", thought)
    return "Thought recorded. Proceed with the next tool."
