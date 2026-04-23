import logging
import os

from src.agent.utils import get_workspace

logger = logging.getLogger(__name__)


def _get_full_workspace_path(filepath: str) -> str:
    """Get full path for a file in the workspace.

    Args:
        filepath: Relative file path

    Returns:
        Full absolute path within workspace
    """
    return _get_full_path(get_workspace(), filepath)


def _get_full_path(base_path: str, filepath: str) -> str:
    """Construct and validate a full path within a base directory.

    This function ensures that the resulting path stays within the base directory
    by removing leading slashes and validating the resolved path.

    Args:
        base_path: Base directory path
        filepath: Relative file path (leading slashes will be stripped)

    Returns:
        Full absolute path if valid, error message if access denied
    """
    # Strip leading slashes to prevent absolute path injection
    clean_path = filepath.lstrip("/")
    full_path = os.path.join(base_path, clean_path)

    # Resolve symlinks and relative paths to prevent directory traversal
    full_path_real = os.path.realpath(full_path)
    path_real = os.path.realpath(base_path)

    # Verify the resolved path is within the base directory
    if not full_path_real.startswith(path_real):
        logger.warning(
            "Path traversal attempt blocked: %s is outside %s", full_path_real, path_real
        )
        return f"Access denied target file: {full_path_real} is not in path {path_real}"

    logger.debug("Validated path: %s -> %s", filepath, full_path_real)
    return full_path


def read_file_in_workspace(filepath: str):
    """Read the content of a file from the workspace.

    Args:
        filepath: Relative path to the file

    Returns:
        File content, empty file message, or error message
    """
    try:
        logger.debug("Reading workspace file: %s", filepath)
        full_path = _get_full_workspace_path(filepath)

        # Check if file exists
        if not os.path.exists(full_path):
            logger.warning("File not found: %s", full_path)
            return (
                f"ERROR: File {full_path} does not exist. "
                + "(Current dir: {os.listdir(WORKSPACE)})"
            )

        # Read file content
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        if not content:
            logger.debug("File is empty: %s", full_path)
            return "(File is empty)"

        logger.debug("Successfully read %d bytes from %s", len(content), full_path)
        return content
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to read file %s: %s", filepath, str(e))
        logger.debug("Read error stacktrace:", exc_info=True)
        return f"ERROR reading file: {str(e)}"


def write_to_file_in_workspace(filepath: str, content: str):
    """Write content to a file in the workspace.

    Creates parent directories if they don't exist.

    Args:
        filepath: Relative path to the file
        content: Content to write

    Returns:
        Success message or error message
    """
    try:
        logger.debug("Writing to workspace file: %s", filepath)
        full_path = _get_full_workspace_path(filepath)

        # Create parent directories if needed
        parent_dir = os.path.dirname(full_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
            logger.debug("Ensured directory exists: %s", parent_dir)

        # Write content to file
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.debug("Successfully wrote %d bytes to %s", len(content), full_path)
        return f"Successfully wrote to {full_path}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to write file %s: %s", filepath, str(e))
        logger.debug("Write error stacktrace:", exc_info=True)
        return f"ERROR writing file: {str(e)}"
