"""A collection of tools for the agent to interact with the implementation plan"""

import logging

from langchain_core.tools import tool

from app.agent.tools.file_tools import write_to_file_in_instance_dir

logger = logging.getLogger(__name__)


@tool
def write_plan(content: str):
    """
    Writes the implementation plan to a file in the instance directory.
    """
    return write_to_file_in_instance_dir("plan.md", content)
