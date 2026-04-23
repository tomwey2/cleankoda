"""A collection of tools for the agent to interact with files"""

from dataclasses import dataclass
import fnmatch
import logging
import os
import re

from langchain_core.tools import tool

from src.agent.utils import get_workspace

logger = logging.getLogger(__name__)


# Ignore patterns for directory traversal
IGNORE_PATTERNS = {
    ".git",
    ".gradle",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "build",
    "dist",
    "target",
    ".idea",
    ".vscode",
    "*.egg-info",
}


@dataclass
class _FileListingContext:
    """Context object for file listing operations.

    Groups related parameters to reduce function argument count and
    maintain state during directory traversal.

    Attributes:
        workspace: Absolute path to workspace directory
        max_files: Maximum number of files to collect
        pattern: Optional glob pattern for filtering files
        content_pattern: Optional regex pattern for filtering by file content
        case_sensitive: Whether content matching should be case-sensitive
        file_list: Accumulated list of matching file paths
        truncated: Flag indicating if max_files limit was reached
    """

    workspace: str
    max_files: int
    pattern: str | None
    content_pattern: str | None
    case_sensitive: bool
    file_list: list[str]
    truncated: bool = False


def _should_skip_directory(
    root: str, dirs: list[str], max_depth: int | None, start_depth: int
) -> bool:
    """Determine if a directory should be skipped during traversal.

    Filters out ignored directories and enforces max depth limit.
    Modifies the dirs list in-place to prevent os.walk from descending.

    Args:
        root: Current directory path being processed
        dirs: List of subdirectories (modified in-place)
        max_depth: Maximum recursion depth (None for unlimited)
        start_depth: Starting depth for relative depth calculation

    Returns:
        True if directory should be skipped, False otherwise
    """
    # Filter ignored directories in-place to prevent os.walk from descending
    original_count = len(dirs)
    dirs[:] = [d for d in dirs if d not in IGNORE_PATTERNS]

    if len(dirs) < original_count:
        logger.debug("Filtered %d ignored directories from %s", original_count - len(dirs), root)

    # Check if current depth exceeds max_depth
    if max_depth is not None:
        current_depth = root.count(os.sep) - start_depth
        if current_depth >= max_depth:
            logger.debug("Max depth %d reached at %s", max_depth, root)
            dirs.clear()  # Prevent further descent
            return True

    # Skip directories containing ignored patterns in their path
    if any(pattern in root for pattern in IGNORE_PATTERNS):
        logger.debug("Skipping directory with ignored pattern: %s", root)
        return True

    return False


def _matches_content_pattern(filepath: str, pattern: str, case_sensitive: bool = False) -> bool:
    """Check if file content matches the given pattern (grep-like).

    Args:
        filepath: Absolute path to the file
        pattern: Regex pattern to search for in file content
        case_sensitive: Whether to perform case-sensitive matching

    Returns:
        True if pattern found in file content, False otherwise
    """
    # Skip files larger than 10MB to avoid performance issues
    max_file_size = 10 * 1024 * 1024  # 10MB
    try:
        file_size = os.path.getsize(filepath)
        if file_size > max_file_size:
            logger.debug(
                "Skipping file %s (size: %d bytes) - exceeds 10MB limit", filepath, file_size
            )
            return False
    except OSError as e:
        logger.warning("Could not get file size for %s: %s", filepath, str(e))
        return False

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        flags = 0 if case_sensitive else re.IGNORECASE
        return bool(re.search(pattern, content, flags))
    except (IOError, OSError, UnicodeDecodeError) as e:
        logger.debug("Could not read file %s for content matching: %s", filepath, str(e))
        return False
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.warning(
            "Unexpected error reading file %s for content matching: %s", filepath, str(e)
        )
        return False


def _process_files_for_listing(root: str, files: list[str], ctx: _FileListingContext) -> None:
    """Process files in a directory for the file listing.

    Applies pattern filtering and enforces max_files limit.
    Updates the context object with matching files.

    Args:
        root: Current directory path
        files: List of files in the directory
        ctx: File listing context (modified in-place)
    """
    for file in files:
        # Check if we've reached the file limit
        if len(ctx.file_list) >= ctx.max_files:
            logger.debug("Reached max_files limit (%d) at %s", ctx.max_files, root)
            ctx.truncated = True
            return

        # Construct relative path from workspace
        rel_path = os.path.relpath(os.path.join(root, file), ctx.workspace)

        # Apply pattern filter if specified
        if ctx.pattern and not fnmatch.fnmatch(rel_path, ctx.pattern):
            logger.debug("File %s does not match pattern %s", rel_path, ctx.pattern)
            continue

        # Apply content pattern filter if specified
        if ctx.content_pattern:
            full_path = os.path.join(root, file)
            if not _matches_content_pattern(full_path, ctx.content_pattern, ctx.case_sensitive):
                logger.debug(
                    "File %s does not match content pattern %s", rel_path, ctx.content_pattern
                )
                continue

        # Add matching file to the list
        ctx.file_list.append(rel_path)
        logger.debug("Added file to list: %s", rel_path)


def _format_summary_result(dir_summary: dict[str, int]) -> str:
    """Format directory summary as a human-readable string.

    Args:
        dir_summary: Dictionary mapping directory paths to file counts

    Returns:
        Formatted summary string
    """
    if not dir_summary:
        logger.debug("No directories found for summary")
        return "No files found."

    # Build summary with sorted directory paths
    result = ["Directory Summary:"]
    for dir_path, count in sorted(dir_summary.items()):
        result.append(f"  {dir_path}: {count} files")

    logger.debug("Generated summary for %d directories", len(dir_summary))
    return "\n".join(result)


def _format_file_list_result(file_list: list[str], truncated: bool, max_files: int) -> str:
    """Format file list as a human-readable string.

    Args:
        file_list: List of file paths
        truncated: Whether the list was truncated due to max_files limit
        max_files: Maximum number of files that were collected

    Returns:
        Formatted file list string with optional truncation notice
    """
    if not file_list:
        logger.debug("No files found to format")
        return "No files found."

    # Join file paths with newlines
    result = "\n".join(file_list)

    # Add truncation notice if applicable
    if truncated:
        logger.debug("File list truncated at %d files", max_files)
        result += (
            f"\n\n[TRUNCATED: Showing first {max_files} files. "
            f"Use max_files parameter to see more, or use summary=True for overview]"
        )
    else:
        logger.debug("Formatted %d files", len(file_list))

    return result


def _validate_directory_access(directory: str, workspace: str) -> str | None:
    """Validate that a directory is within the workspace.

    Prevents directory traversal attacks by ensuring the resolved path
    stays within the workspace boundaries.

    Args:
        directory: Relative directory path to validate
        workspace: Absolute workspace path

    Returns:
        Error message if access denied, None if access is valid
    """
    # Construct and resolve the target directory path
    target_dir = os.path.join(workspace, directory.lstrip("/"))
    target_dir_real = os.path.realpath(target_dir)
    workspace_real = os.path.realpath(workspace)

    # Verify the resolved path is within workspace
    if not target_dir_real.startswith(workspace_real):
        logger.warning(
            "Directory access denied: %s is outside workspace %s",
            target_dir_real,
            workspace_real,
        )
        return "Access denied"

    logger.debug("Directory access validated: %s", target_dir_real)
    return None


@tool
# pylint: disable=too-many-arguments,too-many-locals,too-many-positional-arguments
def dir(
    directory: str = ".",
    max_files: int = 500,
    max_depth: int | None = None,
    summary: bool = False,
    pattern: str | None = None,
    content_pattern: str | None = None,
    case_sensitive: bool = False,
) -> str:
    """
    Lists files in a directory (recursive). Can filter by filename pattern AND/OR by file content.

    Use content_pattern to search for files containing specific text (like grep -r).
    This is useful for finding files with specific imports, functions, classes, or text patterns.

    Args:
        directory: Directory to list (relative to workspace)
        max_files: Maximum number of files to return (default: 500)
        max_depth: Maximum depth to recurse (None = unlimited)
        summary: If True, return directory tree with counts instead of file list
        pattern: Optional glob pattern to filter files by name (e.g., "*.py", "src/**/*.java")
        content_pattern: Optional regex pattern to filter files by content (grep-like).
            Examples: "TODO", "def.*test", "import pandas", "@Override"
        case_sensitive: Whether content_pattern matching should be case-sensitive (default: False)

    Examples:
        - Find all files containing "TODO": content_pattern="TODO"
        - Find Python files with test functions: pattern="*.py", content_pattern="def.*test"
        - Find Java files with specific annotation: pattern="*.java", content_pattern="@Override"
    """
    try:
        logger.debug(
            "dir: directory=%s, max_files=%d, max_depth=%s, "
            "summary=%s, pattern=%s, content_pattern=%s, case_sensitive=%s",
            directory,
            max_files,
            max_depth,
            summary,
            pattern,
            content_pattern,
            case_sensitive,
        )

        # Get workspace and validate directory access
        workspace = get_workspace()
        access_error = _validate_directory_access(directory, workspace)
        if access_error:
            return access_error

        # Prepare for directory traversal
        target_dir = os.path.join(workspace, directory.lstrip("/"))
        start_depth = os.path.realpath(target_dir).count(os.sep)
        dir_summary = {}
        ctx = _FileListingContext(
            workspace=workspace,
            max_files=max_files,
            pattern=pattern,
            content_pattern=content_pattern,
            case_sensitive=case_sensitive,
            file_list=[],
        )

        # Walk directory tree
        logger.debug("Starting directory walk from %s", target_dir)
        for root, dirs, files in os.walk(target_dir):
            # Check if directory should be skipped
            if _should_skip_directory(root, dirs, max_depth, start_depth):
                continue

            if summary:
                # Collect directory file counts for summary mode
                dir_summary[os.path.relpath(root, workspace)] = len(files)
            else:
                # Process files for listing mode
                _process_files_for_listing(root, files, ctx)
                if ctx.truncated:
                    logger.debug("File listing truncated at max_files=%d", max_files)
                    break

        # Format and return results
        if summary:
            logger.debug("dir: Returning directory summary for %d directories", len(dir_summary))
            return _format_summary_result(dir_summary)

        logger.debug("dir: Returning file list with %d files", len(ctx.file_list))
        return _format_file_list_result(ctx.file_list, ctx.truncated, max_files)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to list files in %s: %s", directory, str(e))
        logger.debug("List files error stacktrace:", exc_info=True)
        return str(e)
