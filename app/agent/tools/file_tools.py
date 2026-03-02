"""A collection of tools for the agent to interact with files"""

import fnmatch
import logging
import os
import traceback

from langchain_core.tools import tool

from app.agent.utils import get_instance_dir, get_workspace

logger = logging.getLogger(__name__)


def _get_full_workspace_path(filepath: str) -> str:
    return _get_full_path(get_workspace(), filepath)

def _get_full_instance_path(filepath: str) -> str:
    return _get_full_path(get_instance_dir(), filepath)

def _get_full_path(base_path: str, filepath: str) -> str:
    """Remove leading slashes to prevent absolute paths."""
    # FIX: Remove leading slashes
    clean_path = filepath.lstrip("/")
    full_path = os.path.join(base_path, clean_path)

    full_path_real = os.path.realpath(full_path)
    path_real = os.path.realpath(base_path)
    if not full_path_real.startswith(path_real):
        return f"Access denied target file: {full_path_real} is not in path {path_real}"
    return full_path


def write_to_file_in_workspace(filepath: str, content: str):
    """
    Writes content to a file.
    """
    try:
        full_path = _get_full_workspace_path(filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {full_path}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error writing file %s: %s", full_path, e)
        logger.debug("Write file error stacktrace:\n%s", traceback.format_exc())
        return f"ERROR writing file: {str(e)}"

def write_to_file_in_instance_dir(filepath: str, content: str):
    """
    Writes content to a file in the instance directory.
    """
    try:
        full_path = _get_full_instance_path(filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {full_path}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error writing file %s: %s", full_path, e)
        logger.debug("Write file error stacktrace:\n%s", traceback.format_exc())
        return f"ERROR writing file: {str(e)}"


def read_file_in_workspace(filepath: str):
    """
    Reads the content of a file.
    """
    try:
        full_path = _get_full_workspace_path(filepath)
        if not os.path.exists(full_path):
            return (
                f"ERROR: File {full_path} does not exist. "
                + f"(Current dir: {os.listdir(get_workspace())})"
            )

        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
            if not content:
                return "(File is empty)"
            return content
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error reading file %s: %s", full_path, e)
        logger.debug("Read file error stacktrace:\n%s", traceback.format_exc())
        return f"ERROR reading file: {str(e)}"


@tool
def read_file(filepath: str):
    """
    Reads the content of a file.
    """
    return read_file_in_workspace(filepath)


@tool
def list_files(
    directory: str = ".",
    max_files: int = 500,
    max_depth: int | None = None,
    summary: bool = False,
    pattern: str | None = None
):
    """
    Lists files in a directory (recursive).
    
    Args:
        directory: Directory to list (relative to workspace)
        max_files: Maximum number of files to return (default: 500)
        max_depth: Maximum depth to recurse (None = unlimited)
        summary: If True, return directory tree with counts instead of file list
        pattern: Optional glob pattern to filter files (e.g., "*.py", "src/**/*.java")
    """
    try:
        clean_dir = directory.lstrip("/")
        target_dir = os.path.join(get_workspace(), clean_dir)
        target_dir_real = os.path.realpath(target_dir)
        workspace_real = os.path.realpath(get_workspace())

        if not target_dir_real.startswith(workspace_real):
            logger.warning(
                "Access denied target directory: %s is not in workspace %s",
                target_dir_real,
                workspace_real,
            )
            return "Access denied"

        # Enhanced ignore patterns
        ignore_patterns = {
            ".git", ".gradle", "node_modules", "__pycache__",
            ".pytest_cache", ".venv", "venv", "build", "dist",
            "target", ".idea", ".vscode", "*.egg-info"
        }

        start_depth = target_dir_real.count(os.sep)
        file_list = []
        dir_summary = {}
        truncated = False

        for root, dirs, files in os.walk(target_dir):
            # Filter ignored directories in-place
            dirs[:] = [d for d in dirs if d not in ignore_patterns]

            # Check depth limit
            if max_depth is not None:
                current_depth = root.count(os.sep) - start_depth
                if current_depth >= max_depth:
                    dirs.clear()
                    continue

            # Skip ignored patterns in path
            if any(pattern in root for pattern in ignore_patterns):
                continue

            if summary:
                rel_root = os.path.relpath(root, get_workspace())
                dir_summary[rel_root] = len(files)
            else:
                for file in files:
                    if len(file_list) >= max_files:
                        truncated = True
                        break

                    rel_path = os.path.relpath(os.path.join(root, file), get_workspace())

                    # Apply pattern filter if specified
                    if pattern and not fnmatch.fnmatch(rel_path, pattern):
                        continue

                    file_list.append(rel_path)

                if truncated:
                    break

        if summary:
            if not dir_summary:
                return "No files found."
            result = ["Directory Summary:"]
            for dir_path, count in sorted(dir_summary.items()):
                result.append(f"  {dir_path}: {count} files")
            return "\n".join(result)

        if not file_list:
            return "No files found."

        result = "\n".join(file_list)
        if truncated:
            result += (
                f"\n\n[TRUNCATED: Showing first {max_files} files. "
                f"Use max_files parameter to see more, or use summary=True for overview]"
            )

        return result

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Unexpected error in list_files: %s", e)
        logger.debug("List files error stacktrace:\n%s", traceback.format_exc())
        return str(e)


@tool
def write_to_file(filepath: str, content: str):
    """
    Writes content to a file.
    """
    return write_to_file_in_workspace(filepath, content)
