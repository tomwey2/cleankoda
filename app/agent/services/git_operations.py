"""
Git operations service.

Centralizes git operations (add, commit, push) for better testability
and code reuse across nodes.
"""

import logging
import subprocess

from app.agent.models.node_results import GitOperationResult
from app.agent.utils import get_codespace

logger = logging.getLogger(__name__)


def check_git_status() -> GitOperationResult:
    """
    Check if there are uncommitted changes in the repository.
    
    Returns:
        GitOperationResult with success=True if changes exist
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=get_codespace(),
            check=True,
            capture_output=True,
            text=True,
        )
        has_changes = bool(result.stdout.strip())
        message = "Changes detected" if has_changes else "No changes detected"
        logger.info("Git status check: %s", message)
        return GitOperationResult(success=has_changes, message=message)
    except subprocess.CalledProcessError as e:
        logger.error("Git status failed: %s", e.stderr)
        return GitOperationResult(success=False, message=f"Git status failed: {e.stderr}")


def git_add_all() -> GitOperationResult:
    """
    Stage all changes for commit.
    
    Returns:
        GitOperationResult indicating success or failure
    """
    try:
        subprocess.run(
            ["git", "add", "."],
            cwd=get_codespace(),
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Git add successful")
        return GitOperationResult(success=True, message="All changes staged")
    except subprocess.CalledProcessError as e:
        logger.error("Git add failed: %s", e.stderr)
        return GitOperationResult(success=False, message=f"Git add failed: {e.stderr}")


def git_commit(message: str) -> GitOperationResult:
    """
    Commit staged changes with the given message.
    
    Args:
        message: Commit message
        
    Returns:
        GitOperationResult indicating success or failure
    """
    try:
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=get_codespace(),
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Git commit successful: %s", message)
        return GitOperationResult(success=True, message=result.stdout.strip())
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or e.stdout or "Unknown error"
        logger.error("Git commit failed: %s", error_msg)
        return GitOperationResult(success=False, message=f"Git commit failed: {error_msg}")


def git_push() -> GitOperationResult:
    """
    Push commits to the remote repository.
    
    Returns:
        GitOperationResult indicating success or failure
    """
    try:
        result = subprocess.run(
            ["git", "push", "--set-upstream", "origin", "HEAD"],
            cwd=get_codespace(),
            check=True,
            capture_output=True,
            text=True,
        )
        output = result.stdout.strip() or result.stderr.strip()
        logger.info("Git push successful: %s", output)
        return GitOperationResult(success=True, message=output)
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or e.stdout or "Unknown error"
        logger.error("Git push failed: %s", error_msg)
        return GitOperationResult(success=False, message=error_msg)
