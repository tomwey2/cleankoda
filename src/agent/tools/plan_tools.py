"""A collection of tools for the agent to interact with the implementation plan"""

import logging

from langchain_core.tools import tool

from src.core.services.plan_service import save_plan_to_db

logger = logging.getLogger(__name__)


@tool
def write_plan(content: str):
    """
    Writes the implementation plan to a file in the instance directory.
    """
    if not save_plan_to_db(content):
        return "No issue in database found. Can not store the plan."
    return "Successfully wrote plan to database"
