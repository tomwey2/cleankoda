"""Create a checkout node"""

import logging
import re
from typing import Any, Dict

from git import Repo

from src.agent.services.git_workspace import checkout_branch, get_current_branch
from src.agent.state import AgentState
from src.agent.utils import get_workspace
from src.core.database.models import AgentSettingsDb
from src.core.types import IssueType

logger = logging.getLogger(__name__)

ROLE_PREFIXES = {
    IssueType.CODING: "feature",
    IssueType.BUGFIXING: "bugfix",
}


def create_checkout_node(agent_settings: AgentSettingsDb):
    """Create a checkout node"""

    async def checkout_node(state: AgentState) -> Dict[str, Any]:  # pylint: disable=unused-argument
        if state["current_node"] != "checkout":
            logger.info("--- CHECKOUT node ---")
        issue_type = IssueType.from_string(
            state.get("issue_type") if state.get("issue_id") else IssueType.CODING
        )
        if state.get("issue_id"):
            repo_branch_name = await _checkout_issue_branch(
                state,
                state["issue_id"],
                state["issue_name"],
                issue_type,
                agent_settings,
            )
            return {"current_node": "checkout", "repo_branch_name": repo_branch_name}

        raise ValueError("Missing issue_id or issue_name in AgentState")

    return checkout_node


async def _checkout_issue_branch(
    state: AgentState,
    issue_id: str,
    issue_name: str,
    issue_type: IssueType,
    agent_settings: AgentSettingsDb,
) -> str | None:
    """
    Checks out the existing git branch for a issue from the database.
    Returns the repo branch name.
    """

    if issue_type not in [IssueType.CODING, IssueType.BUGFIXING]:
        repo = Repo(get_workspace())
        repo.git.fetch()
        repo.git.reset("--hard")
        return

    repo_branch_name = state["repo_branch_name"]

    if not repo_branch_name:
        logger.info("No git branch found for issue %s", issue_id)
        repo_branch_name = await _checkout_branch_for_issue(
            issue_id, issue_name, issue_type, agent_settings
        )
    else:
        logger.info(
            "Checking out existing git branch: %s for issue %s - %s",
            repo_branch_name,
            issue_id,
            issue_name,
        )

        if agent_settings.repo_url:
            checkout_branch(agent_settings.repo_url, repo_branch_name, get_workspace())
        else:
            logger.warning("No repo_url in agent settings, skipping checkout")

        real_git_branch = get_current_branch(get_workspace())
        logger.info("Current branch: %s", real_git_branch)

    return repo_branch_name


def _slugify(value: str | None) -> str:
    """
    Convert a string to a branch-friendly slug.
    """
    if not value:
        return ""
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


def _build_base_repo_branch_name(issue_id: str, issue_name: str, issue_type: IssueType) -> str:
    slug = _slugify(issue_name)
    sanitized_issue_id = re.sub(r"[^a-z0-9]", "", issue_id.lower())
    short_id = sanitized_issue_id[:8] if sanitized_issue_id else "issue"
    branch_suffix = slug[:48] if slug else "update"
    role_prefix = ROLE_PREFIXES.get(issue_type, "feature")
    return f"agent/{role_prefix}/{short_id}-{branch_suffix}"


def _collect_repo_branch_names(repo: Repo) -> set[str]:
    names = {head.name for head in repo.heads}
    for remote in repo.remotes:
        for ref in remote.refs:
            remote_name = getattr(ref, "remote_head", None)
            if remote_name:
                names.add(remote_name)
            else:
                names.add(ref.name.split("/")[-1])
    return names


def _resolve_unique_repo_branch_name(base_name: str, existing_names: set[str]) -> str:
    candidate = base_name
    suffix_counter = 1
    while candidate in existing_names:
        candidate = f"{base_name}-{suffix_counter}"
        suffix_counter += 1
    if candidate != base_name:
        logger.info(
            "Branch name conflict detected. Using '%s' instead of '%s'.",
            candidate,
            base_name,
        )
    return candidate


async def _checkout_branch_for_issue(
    issue_id: str, issue_name: str, issue_type: IssueType, agent_settings: AgentSettingsDb
) -> str | None:
    """
    Checks out a new git branch for an issue.
    The branch name is derived from the issue name and guaranteed to be unique.
    Includes role-specific prefixes for clarity.
    Returns the repo branch name.
    """
    if not issue_id or not issue_name:
        raise ValueError("issue_id and issue_name are required to create a git branch.")

    repo = Repo(get_workspace())
    repo.git.reset("--hard")
    repo.git.fetch("--prune")

    base_repo_branch_name = _build_base_repo_branch_name(issue_id, issue_name, issue_type)
    existing_branches = _collect_repo_branch_names(repo)
    repo_branch_name = _resolve_unique_repo_branch_name(base_repo_branch_name, existing_branches)

    if not agent_settings.repo_url:
        logger.warning(
            "No repo_url in agent settings, cannot checkout branch for issue %s", issue_id
        )
        return None

    logger.info(
        "Creating git branch '%s' for issue %s - %s",
        repo_branch_name,
        issue_id,
        issue_name,
    )

    repo.git.reset("--hard")
    repo.git.checkout("-b", repo_branch_name)

    real_git_branch = get_current_branch(get_workspace())
    logger.info("Current branch after checkout: %s", real_git_branch)
    return repo_branch_name
