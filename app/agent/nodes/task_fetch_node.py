"""
Task fetch node.

Fetches tasks from a board system (Trello, GitHub, Jira, etc.),
preparing them for processing by the agent.
"""

import logging
from datetime import datetime

from core.task_repository import remove_task_from_db
from langchain_core.messages import HumanMessage

from agent.integrations.board_factory import create_board_provider
from agent.integrations.board_provider import BoardProvider, BoardTask  # pylint: disable=unused-import
from agent.state import AgentState

logger = logging.getLogger(__name__)


async def _get_task_context(board_provider: BoardProvider, sys_config: dict):
    incoming_list_name = sys_config["task_readfrom_list"]
    in_progress_list_name = sys_config.get("task_in_progress_list")

    task_context = None
    if in_progress_list_name:
        task_context = await fetch_task_from_list(
            board_provider, in_progress_list_name, sys_config
        )

    if not task_context:
        task_context = await fetch_task_from_list(
            board_provider, incoming_list_name, sys_config
        )
    return task_context


async def _ensure_task_in_progress(
    board_provider: BoardProvider,
    task_context: dict,
    task_id: str,
    task_in_progress_list_name: str | None,
    sys_config: dict,
) -> dict:
    """
    Moves the task to the in-progress list if needed, updating the task_context.
    """
    if not task_in_progress_list_name:
        return task_context

    current_list_name = task_context["list_name"]
    if current_list_name == task_in_progress_list_name:
        return task_context

    remove_task_from_db(task_id)
    readfrom_list_id = task_context["list_id"]
    move_task_result = await move_task_to_in_progress(
        board_provider, task_id, readfrom_list_id, task_in_progress_list_name, sys_config
    )
    task_context["list_id"] = move_task_result["list_id"]
    return task_context


def create_task_fetch_node(sys_config: dict):
    """Creates a task fetch node for the agent graph."""

    async def task_fetch(state: AgentState) -> dict:  # pylint: disable=unused-argument
        """
        Fetches the first task from the board in a specified list.
        """
        logger.info("Fetching tasks from board")

        try:
            board_provider = create_board_provider(sys_config)

            review_list_name = sys_config.get("task_moveto_list")
            if not review_list_name:
                return {"task_id": None}

            task_in_progress_list_name = sys_config.get("task_in_progress_list")

            task_context = await _get_task_context(board_provider, sys_config)
            if not task_context:
                return {"task_id": None}

            task = task_context["task"]

            task_context = await _ensure_task_in_progress(
                board_provider,
                task_context,
                task.id,
                task_in_progress_list_name,
                sys_config,
            )

            comments = await board_provider.get_comments(task.id)

            review_cutoff = await get_review_transition_timestamp(
                board_provider, task.id, review_list_name
            )
            if review_cutoff:
                comments = filter_comments_after_timestamp(comments, review_cutoff)

            content = task.name + "\n" + task.description
            if comments:
                content += (
                    "\n\n--- The Pull Request was rejected with "
                    + "the following comments: ---\n"
                )
                for comment in reversed(comments):
                    author = comment.author
                    text = comment.text
                    date = comment.date.isoformat()
                    content += f"\n[{date}] {author}:\n{text}\n"

            logger.info("Processing task ID: %s - %s", task.id, task.name)
            logger.info("Initial messages content: %s", content)

            return {
                "task_id": task.id,
                "task_name": task.name,
                "messages": [HumanMessage(content=content)],
                "task_state_id": task_context["list_id"],
                "agent_summary": [],
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error fetching tasks: %s", e)
            return {"task_id": None}

    return task_fetch


async def fetch_task_from_list(
    board_provider: BoardProvider, readfrom_list_name: str, sys_config: dict  # pylint: disable=unused-argument
) -> dict | None:
    """Fetch a task from a board list."""
    board_lists = await board_provider.get_lists()
    read_from_list = next(
        (data for data in board_lists if data["name"] == readfrom_list_name),
        None,
    )

    if not read_from_list:
        logger.warning("%s list not found", readfrom_list_name)
        return None

    readfrom_list_id = read_from_list["id"]
    logger.info("Found %s list id: %s", readfrom_list_name, readfrom_list_id)

    tasks = await board_provider.get_tasks_from_list(readfrom_list_id)
    if not tasks:
        logger.info("No open tasks found in %s.", readfrom_list_name)
        return None

    task = tasks[0]

    return {
        "task": task,
        "list_id": readfrom_list_id,
        "list_name": readfrom_list_name,
    }


async def move_task_to_in_progress(
    board_provider: BoardProvider,
    task_id: str,
    current_list_id: str,
    task_in_progress_list_name: str,
    sys_config: dict,  # pylint: disable=unused-argument
) -> dict:
    """
    Moves the task to the in-progress list before task processing begins.
    """
    if not task_in_progress_list_name:
        logger.warning(
            "task_in_progress_list not configured, skipping move to in-progress list"
        )
    else:
        logger.info(
            "Moving task %s to in-progress list: %s", task_id, task_in_progress_list_name
        )

        try:
            progress_list_id = await board_provider.move_task_to_named_list(
                task_id, task_in_progress_list_name
            )
            return {
                "list_id": progress_list_id,
            }
        except ValueError as e:
            logger.warning("Failed to move task to in-progress list: %s", e)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to move task to in-progress list: %s", e)

    return {"list_id": current_list_id}


async def get_review_transition_timestamp(
    board_provider: BoardProvider, task_id: str, review_list_name: str
) -> datetime | None:
    """Returns the timestamp of the last transition of a task to a review list."""
    try:
        list_moves = await board_provider.get_list_moves(task_id)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.warning(
            "Failed to fetch list moves for task %s: %s. Including all comments.",
            task_id,
            e,
        )
        return None

    review_timestamps = [
        move.date
        for move in list_moves
        if move.list_after == review_list_name
    ]
    if not review_timestamps:
        return None

    latest_review = max(review_timestamps)
    logger.info(
        "Task %s last moved to '%s' at %s.",
        task_id,
        review_list_name,
        latest_review.isoformat(),
    )
    return latest_review


def filter_comments_after_timestamp(
    comments: list, cutoff: datetime
) -> list:
    """Filters comments after a given timestamp."""
    filtered_comments = []
    for comment in comments:
        if comment.date >= cutoff:
            filtered_comments.append(comment)
    return filtered_comments
