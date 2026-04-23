"""An agent tool to write files"""

from langchain_core.tools import tool

from src.agent.services.file_services import write_to_file_in_workspace


@tool
def write(filepath: str, content: str):
    """
    Writes content to a file.

    WARNING: This replaces the ENTIRE file content. If you only want to modify
    specific lines, read the full file first, make your changes, then write the complete content.
    """

    return write_to_file_in_workspace(filepath, content)
