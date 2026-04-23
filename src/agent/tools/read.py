"""An agent tool to read files"""

from langchain_core.tools import tool

from src.agent.services.file_services import read_file_in_workspace


@tool
def read_file(filepath: str) -> str:
    """
    Reads the entire content of a file.

    Args:
        filepath: Path to the file to read

    Returns:
        Complete file content
    """
    return read_file_in_workspace(filepath)
