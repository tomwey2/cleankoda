"""Tool for signaling task completion."""

from langchain_core.tools import tool


@tool
def finish_task(summary: str):  # pylint: disable=unused-argument
    """Call when the issue is completely finished, providing a summary."""
    return "Issue marked as finished."
