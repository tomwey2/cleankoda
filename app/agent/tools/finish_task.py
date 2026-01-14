"""Tool for signaling task completion."""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def finish_task(summary: str):  # pylint: disable=unused-argument
    """Call when the task is completely finished, providing a summary."""
    return "Task marked as finished."
