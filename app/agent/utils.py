"""General-purpose utilities for workspace management and repository operations."""

from __future__ import annotations

import logging
import os
import shutil
from urllib.parse import urlparse, urlunparse

from git import Repo
from git.exc import GitCommandError

logger = logging.getLogger(__name__)

__all__ = [
    "checkout_branch",
    "ensure_repository_exists",
    "get_workbench",
    "get_workspace",
    "load_system_prompt",
    "normalize_git_url",
    "save_graph_as_mermaid",
    "save_graph_as_png",
]


def get_workspace() -> str:
    """Return the configured workspace path or a sensible default."""
    return os.environ.get("WORKSPACE", "/coding-agent-workspace")


def get_workbench() -> str:
    """Return the active workbench identifier (e.g., 'workbench-backend')."""
    return os.environ.get("WORKBENCH", "")


def load_system_prompt(stack: str, role: str) -> str:
    """
    Load the system prompt for the given stack and role.
    Falls back to a generic helper message if no prompt is available.
    """
    file_path = os.path.join("workbench", stack, f"systemprompt_{role}.md")

    logger.info("Loading system prompt: %s", file_path)
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        logger.warning("WARNUNG: System Prompt not found: %s", file_path)
        return "You are a helpful coding assistent."


def save_graph_as_png(graph) -> None:
    """Persist the compiled LangGraph as a PNG asset."""
    png_bytes = graph.get_graph().draw_mermaid_png()
    with open("workflow_graph.png", "wb") as handle:
        handle.write(png_bytes)
    print("Graph wurde als 'workflow_graph.png' gespeichert.")


def save_graph_as_mermaid(graph) -> None:
    """Persist the compiled LangGraph as Mermaid markup."""
    mermaid_code = graph.get_graph().draw_mermaid()
    with open("workflow_graph.mmd", "w", encoding="utf-8") as handle:
        handle.write(mermaid_code)
    print("Graph wurde als 'workflow_graph.mmd' gespeichert.")


def normalize_git_url(url: str) -> str:
    """
    Normalize a Git URL by removing credentials (username/password/token).
    This allows comparing repository URLs without authentication noise.
    """
    try:
        parsed = urlparse(url)
        normalized = parsed._replace(
            netloc=parsed.hostname + (f":{parsed.port}" if parsed.port else "")
        )
        return urlunparse(normalized)
    except Exception:  # pylint: disable=broad-exception-caught
        return url.split("@")[-1] if "@" in url else url


def ensure_repository_exists(repo_url: str, work_dir: str) -> None:
    """
    Ensure that work_dir contains a clean checkout of repo_url.
    Re-clones when a different repository is detected; otherwise fetches/cleans.
    """

    def clean_and_clone() -> None:
        for filename in os.listdir(work_dir):
            file_path = os.path.join(work_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("Failed to delete %s. Reason: %s", file_path, exc)
        logger.info("Cloning repository %s into %s", repo_url, work_dir)
        Repo.clone_from(repo_url, work_dir)

    git_dir = os.path.join(work_dir, ".git")
    if not os.path.isdir(git_dir):
        logger.info("No git repository found in %s, cloning...", work_dir)
        clean_and_clone()
        return

    try:
        repo = Repo(work_dir)

        try:
            origin_url = repo.remotes.origin.url
        except AttributeError:
            logger.warning("No origin remote found in %s, re-cloning...", work_dir)
            clean_and_clone()
            return

        normalized_origin = normalize_git_url(origin_url)
        normalized_requested = normalize_git_url(repo_url)

        if normalized_origin != normalized_requested:
            logger.info(
                "Different repository detected (current: %s, requested: %s), re-cloning...",
                normalized_origin,
                normalized_requested,
            )
            clean_and_clone()
            return

        logger.info(
            "Repository %s already exists in %s, updating...", repo_url, work_dir
        )

        if repo.is_dirty(untracked_files=True):
            logger.info("Committing local changes...")
            repo.git.add(A=True)
            repo.index.commit("Auto-commit: local changes before fetch")

        logger.info("Fetching origin...")
        repo.remotes.origin.fetch()

        try:
            default_branch = repo.remotes.origin.refs.HEAD.ref.name.replace(
                "origin/", ""
            )
            logger.info("Checking out default branch: %s", default_branch)
            repo.git.checkout(default_branch)
            repo.git.reset("--hard", f"origin/{default_branch}")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning(
                "Could not checkout default branch: %s, staying on current branch", exc
            )

        logger.info("Repository is ready with clean checkout")

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Error managing repository in %s: %s, re-cloning...", work_dir, exc)
        clean_and_clone()


def checkout_branch(repo_url: str, branch_name: str, work_dir: str) -> None:
    """
    Ensure the requested branch is checked out in work_dir.
    Fetches from origin if the branch is not present locally.
    """
    if not branch_name:
        raise ValueError("branch_name is required to checkout a branch.")

    if not os.path.isdir(os.path.join(work_dir, ".git")):
        raise RuntimeError(
            f"No git repository found in {work_dir}. Run ensure_repository_exists first."
        )

    try:
        repo = Repo(work_dir)
    except Exception as exc:
        logger.error("Failed to load repository at %s: %s", work_dir, exc)
        raise

    try:
        if branch_name in repo.heads:
            logger.info("Checking out existing local branch '%s'.", branch_name)
            repo.git.checkout(branch_name)
            return

        logger.info(
            "Local branch '%s' not found. Fetching from origin for repository %s.",
            branch_name,
            repo_url,
        )
        repo.remotes.origin.fetch(branch_name)
        remote_ref = f"origin/{branch_name}"
        if remote_ref in repo.refs:
            repo.git.checkout("-b", branch_name, remote_ref)
            logger.info("Checked out tracking branch '%s' from origin.", branch_name)
            return

        logger.info(
            "Remote branch '%s' not found. Creating new local branch '%s' from current HEAD.",
            remote_ref,
            branch_name,
        )
        repo.git.checkout("-b", branch_name)
        logger.info("Created new local branch '%s'.", branch_name)
    except GitCommandError as exc:
        logger.error("Failed to checkout branch '%s': %s", branch_name, exc)
        raise
