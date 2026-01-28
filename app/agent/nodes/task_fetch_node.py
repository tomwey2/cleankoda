"""
Task fetch node.

Fetches tasks from a board system (Trello, GitHub, Jira, etc.),
preparing them for processing by the agent.
"""

import logging

from langchain_core.messages import SystemMessage

from app.agent.integrations.board_factory import create_board_provider
from app.agent.models.node_results import TaskResolutionResult, PRReviewInfo
from app.agent.services.tasks_services import (
    fetch_review_comments,
    fetch_task_from_state,
    get_branch_for_task,
    move_task_to_state,
)


from app.core.task_repository import get_pr_info_for_task, remove_task_from_db
from app.agent.services.pull_request import (
    format_pr_review_message,
    get_latest_open_pr_for_branch,
    get_latest_pr_review_status,
)

from app.agent.state import AgentState
from app.core.models import AgentSettings
from app.core.plan_services import delete_plan

logger = logging.getLogger(__name__)


def create_task_fetch_node(agent_settings: AgentSettings):
    """Creates a task fetch node for the agent graph."""

    async def task_fetch(state: AgentState) -> dict:  # pylint: disable=unused-argument
        """
        Fetches the first task from the board in a specified list.
        """
        logger.info("Fetching tasks from board")

        try:
            board_provider = create_board_provider(agent_settings)

            active_task_system = agent_settings.get_active_task_system()
            if not active_task_system:
                logger.warning("No active task system configured")
                return {"task": None}

            if not active_task_system.state_in_review:
                logger.warning("No review state configured in task system")
                return {"task": None}

            resolution: TaskResolutionResult = await _resolve_task(
                board_provider,
                active_task_system.state_in_progress,
                active_task_system.state_todo,
                active_task_system.state_in_review,
            )

            if not resolution.task:
                logger.info("There is no current task to work on.")
                return {"task": None}

            logger.info("Processing task ID: %s - %s", resolution.task.id, resolution.task.name)

            system_content = _build_system_message_content(
                resolution.task.name,
                resolution.task.description,
                resolution.comments,
                resolution.pr_review_message,
            )
            result = {
                "task": resolution.task,
                "messages": [SystemMessage(content=system_content)],
                "task_comments": resolution.comments,
                "current_node": "task_fetch",
            }
            result["git_branch"] = resolution.git_branch or ""
            return result

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error fetching tasks: %s", e)
            return {"task_id": None}

    return task_fetch


async def _resolve_task(
    board_provider,
    in_progress_state: str,
    todo_state: str,
    review_state: str,
) -> TaskResolutionResult:
    """
    Resolve which task to work on: either continue in-progress task or fetch new from todo.

    Returns:
        TaskResolutionResult with task, comments, PR review message, and git branch
    """
    task_in_progress = await fetch_task_from_state(board_provider, in_progress_state)

    if task_in_progress:
        logger.info(
            "found task id: %s, state: %s",
            task_in_progress.id,
            task_in_progress.state_name,
        )
        logger.info("task is in progress and add comments")
        comments = await fetch_review_comments(
            board_provider,
            task_in_progress.id,
            in_progress_state,
            review_state,
        )
        pr_info: PRReviewInfo = _fetch_pr_review_info(task_in_progress.id)
        branch_name = get_branch_for_task(task_in_progress.id)
        return TaskResolutionResult(
            task=task_in_progress,
            comments=comments,
            pr_review_message=pr_info.formatted_message,
            git_branch=branch_name,
        )

    logger.info("fetch new task from todo")
    task = await fetch_task_from_state(board_provider, todo_state)
    if task:
        removed = remove_task_from_db(task.id)
        if removed:
            logger.info("Removed stale task %s from DB before reassignment", task.id)
        task = await move_task_to_state(board_provider, task, in_progress_state)
        logger.info("Moved task to %s", task.state_name)
        delete_plan()

    return TaskResolutionResult(
        task=task,
        comments=[],
        pr_review_message="",
        git_branch=None,
    )


def _fetch_pr_review_info(task_id: str) -> PRReviewInfo:
    """
    Fetch PR review info if a PR exists for the task.

    Args:
        task_id: The task ID to check

    Returns:
        PRReviewInfo with approval status and formatted message
    """
    pr_number, pr_url = get_pr_info_for_task(task_id)

    if not pr_number:
        branch_name = get_branch_for_task(task_id)
        if branch_name:
            pr = get_latest_open_pr_for_branch(branch_name)
            if pr:
                pr_number = pr.number
                pr_url = pr.html_url

    if not pr_number:
        logger.info("No PR found for task %s", task_id)
        return PRReviewInfo(is_approved=True, formatted_message="")

    is_approved, rejection_reviews, code_comments = get_latest_pr_review_status(
        pr_number
    )

    if is_approved:
        logger.info("PR #%d for task %s is approved", pr_number, task_id)
        return PRReviewInfo(
            is_approved=True,
            formatted_message="",
            pr_number=pr_number,
            pr_url=pr_url,
        )

    logger.info(
        "PR #%d for task %s has %d rejections and %d code comments",
        pr_number,
        task_id,
        len(rejection_reviews),
        len(code_comments),
    )

    return PRReviewInfo(
        is_approved=False,
        formatted_message=format_pr_review_message(
            pr_url or "", rejection_reviews, code_comments
        ),
        pr_number=pr_number,
        pr_url=pr_url,
    )


def _build_system_message_content(
    task_name: str,
    task_description: str,
    comments: list,
    pr_review_message: str = "",
) -> str:
    """
    Build the system message content including task details and optional review comments.

    Args:
        task_name: Name of the task
        task_description: Description of the task
        comments: List of board review comments (may be empty)
        pr_review_message: Formatted PR review feedback (may be empty)

    Returns:
        Formatted system message content string
    """
    system_content = f"Task: {task_name}\n\nDescription:\n{task_description}"

    if comments:
        system_content += (
            "\n\n--- The Pull Request was rejected with "
            + "the following review comments: ---\n"
            + "NOTE: The task description shows the current implementation. "
            + "The comments below indicate ADDITIONAL work that needs to be done.\n"
        )
        for comment in reversed(comments):
            author = comment.author
            text = comment.text
            date = comment.date.isoformat()
            system_content += f"\n[{date}] {author}:\n{text}\n"

        logger.info("Board review message content: %s", system_content)

    if pr_review_message:
        system_content += pr_review_message
        logger.info("PR review message appended: %s", pr_review_message)

    return system_content
