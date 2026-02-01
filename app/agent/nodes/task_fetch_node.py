"""
Task fetch node.

Fetches tasks from a board system (Trello, GitHub, Jira, etc.),
preparing them for processing by the agent.
"""

import logging
from typing import Optional

from langchain_core.messages import HumanMessage

from app.agent.integrations.board_factory import (
    create_board_provider,
)

from app.agent.integrations.board_provider import BoardTask

from app.agent.models.node_results import PRReviewInfo, TaskResolveResult
from app.agent.services.pull_request import (
    format_pr_review_message,
    get_latest_open_pr_for_branch,
    get_latest_pr_review_status,
)
from app.agent.services.tasks_services import (
    fetch_review_comments,
    fetch_task_from_state,
    get_branch_for_task,
    move_task_to_state,
)
from app.agent.state import AgentState
from app.core.models import AgentSettings, Task
from app.core.task_repository import get_pr_info_for_task, remove_task_from_db

logger = logging.getLogger(__name__)


def create_task_fetch_node(agent_settings: AgentSettings, db_task: Optional[Task]):
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

            task_result: TaskResolveResult = await _resolve_task(
                board_provider,
                active_task_system.state_in_progress,
                active_task_system.state_todo,
                active_task_system.state_in_review,
                db_task,
            )

            if not task_result.task:
                logger.info("There is no current task to work on.")
                return {
                    "task": None,
                    "messages": [],
                    "task_comments": task_result.comments,
                    "git_branch": task_result.git_branch or "",
                    "current_node": "task_fetch",
                }

            logger.info(
                "Processing task ID: %s - %s", task_result.task.id, task_result.task.name
            )

            message_content = _build_message_content(
                task_result.task.name,
                task_result.task.description,
                task_result.comments,
                task_result.pr_review_message,
            )
            result = {
                "task": task_result.task,
                "messages": [HumanMessage(content=message_content)],
                "task_comments": task_result.comments,
                "current_node": "task_fetch",
            }
            result["git_branch"] = task_result.git_branch or ""
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
    db_task: Optional[Task],
) -> TaskResolveResult:
    """
    Resolve which task to work on: either continue in-progress task or fetch new from todo.

    Returns:
        TaskResolveResult with task, comments, PR review message, and git branch
    """

    logger.info("db_task: %s", db_task)
    resumed_task = await _resume_existing_task(
        board_provider,
        in_progress_state,
        review_state,
        db_task,
    )
    if resumed_task is not None:
        return resumed_task

    return await _assign_new_task(board_provider, in_progress_state, todo_state)


async def _resume_existing_task(
    board_provider,
    in_progress_state: str,
    review_state: str,
    db_task: Optional[Task],
) -> TaskResolveResult | None:

    if not db_task or not db_task.task_id:
        return None

    task: Optional[BoardTask] = await board_provider.get_task(db_task.task_id)
    if not task:
        logger.info("Task %s (%s) not found on board", db_task.task_id, db_task.task_name)
        remove_task_from_db(db_task.task_id)
        return None

    if task.state_name == review_state:
        logger.info(
            "Task %s (%s) is in review state %s, waiting for human action",
            task.id,
            task.name,
            review_state,
        )
        return _empty_resolution()

    if task.state_name != in_progress_state:
        removed = remove_task_from_db(task.id)
        if removed:
            logger.info(
                "Removed stale task %s (%s) because it moved to %s",
                task.id,
                task.name,
                task.state_name,
            )
        return None

    logger.info("found task id: %s (%s), state: %s", task.id, task.name, task.state_name)
    comments = await fetch_review_comments(
        board_provider,
        task.id,
        in_progress_state,
        review_state,
    )
    pr_info: PRReviewInfo = _fetch_pr_review_info(task.id)

    branch_name = get_branch_for_task(task.id)
    return TaskResolveResult(
        task=task,
        comments=comments,
        pr_review_message=pr_info.formatted_message,
        git_branch=branch_name,
    )


async def _assign_new_task(
    board_provider,
    in_progress_state: str,
    todo_state: str,
) -> TaskResolveResult:
    logger.info("fetch new task from todo")
    task = await fetch_task_from_state(board_provider, todo_state)
    if not task:
        return _empty_resolution()

    task = await move_task_to_state(board_provider, task, in_progress_state)
    logger.info("Moved task to %s", task.state_name)
    # delete plan.md
    return TaskResolveResult(
        task=task,
        comments=[],
        pr_review_message="",
        git_branch=None,
    )


def _empty_resolution() -> TaskResolveResult:
    return TaskResolveResult(
        task=None,
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


def _build_message_content(
    task_name: str,
    task_description: str,
    comments: list,
    pr_review_message: str = "",
) -> str:
    """
    Build the message content including task details and optional review comments.

    Args:
        task_name: Name of the task
        task_description: Description of the task
        comments: List of board review comments (may be empty)
        pr_review_message: Formatted PR review feedback (may be empty)

    Returns:
        Formatted message content string
    """
    message_content = f"Task: {task_name}\n\nDescription:\n{task_description}"

    if comments:
        message_content += (
            "\n\n--- The Pull Request was rejected with "
            + "the following review comments: ---\n"
            + "NOTE: The task description shows the current implementation. "
            + "The comments below indicate ADDITIONAL work that needs to be done.\n"
        )
        for comment in reversed(comments):
            author = comment.author
            text = comment.text
            date = comment.date.isoformat()
            message_content += f"\n[{date}] {author}:\n{text}\n"

        logger.info("Board review message content: %s", message_content)

    if pr_review_message:
        message_content += pr_review_message
        logger.info("PR review message appended: %s", pr_review_message)

    return message_content
