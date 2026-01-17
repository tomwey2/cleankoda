"""
Database repository functions for managing tasks and their corresponding branches.
"""

from typing import Optional

from core.extensions import db
from core.models import Task


def get_branch_for_task(task_id: str) -> Optional[str]:
    """
    Retrieves the branch name associated with a task ID.
    Returns None if no mapping exists.
    """
    task = Task.query.filter_by(task_id=task_id).first()
    return task.branch_name if task else None


def upsert_task(
    task_id: str, task_name: str, branch_name: str, repo_url: str | None = None
) -> Task:
    """
    Creates or updates a Task record for a task.
    If a task with the given task_id exists, updates it; otherwise creates a new one.
    """
    task = Task.query.filter_by(task_id=task_id).first()

    if task:
        task.task_name = task_name
        task.branch_name = branch_name
        if repo_url:
            task.repo_url = repo_url
    else:
        task = Task(
            task_id=task_id,
            task_name=task_name,
            branch_name=branch_name,
            repo_url=repo_url,
        )
        db.session.add(task)

    db.session.commit()
    return task


def get_task_by_id(task_id: str) -> Optional[Task]:
    """
    Retrieves the full Task record for a given task ID.
    Returns None if no mapping exists.
    """
    return Task.query.filter_by(task_id=task_id).first()


def remove_task_from_db(task_id: str) -> bool:
    """
    Removes the task mapping from the database.
    Returns True if a record was deleted, False otherwise.
    """
    task = Task.query.filter_by(task_id=task_id).first()

    if task:
        db.session.delete(task)
        db.session.commit()
        return True

    return False
