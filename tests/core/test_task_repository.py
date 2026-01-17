"""
Tests for the task repository.
"""

import pytest

from core.models import Task
from core.task_repository import (
    get_branch_for_task,
    get_task_by_id,
    remove_task_from_db,
    upsert_task,
)


@pytest.fixture
def app_context(app):
    """Fixture to provide Flask app context."""
    with app.app_context():
        yield


def test_upsert_task_create_new(app_context, db_session):
    """Test creating a new task."""
    task = upsert_task(
        task_id="task123",
        task_name="Test Task",
        branch_name="feature/test-branch",
        repo_url="https://github.com/test/repo",
    )
    
    assert task.task_id == "task123"
    assert task.task_name == "Test Task"
    assert task.branch_name == "feature/test-branch"
    assert task.repo_url == "https://github.com/test/repo"


def test_upsert_task_update_existing(app_context, db_session):
    """Test updating an existing task."""
    upsert_task(
        task_id="task123",
        task_name="Original Name",
        branch_name="feature/original",
    )
    
    updated_task = upsert_task(
        task_id="task123",
        task_name="Updated Name",
        branch_name="feature/updated",
    )
    
    assert updated_task.task_name == "Updated Name"
    assert updated_task.branch_name == "feature/updated"
    
    all_tasks = Task.query.filter_by(task_id="task123").all()
    assert len(all_tasks) == 1


def test_get_branch_for_task_exists(app_context, db_session):
    """Test getting branch for an existing task."""
    upsert_task(
        task_id="task123",
        task_name="Test Task",
        branch_name="feature/test-branch",
    )
    
    branch = get_branch_for_task("task123")
    assert branch == "feature/test-branch"


def test_get_branch_for_task_not_exists(app_context, db_session):
    """Test getting branch for a non-existent task."""
    branch = get_branch_for_task("nonexistent")
    assert branch is None


def test_get_task_by_id_exists(app_context, db_session):
    """Test getting a task by ID when it exists."""
    upsert_task(
        task_id="task123",
        task_name="Test Task",
        branch_name="feature/test-branch",
    )
    
    task = get_task_by_id("task123")
    assert task is not None
    assert task.task_id == "task123"
    assert task.task_name == "Test Task"


def test_get_task_by_id_not_exists(app_context, db_session):
    """Test getting a task by ID when it doesn't exist."""
    task = get_task_by_id("nonexistent")
    assert task is None


def test_remove_task_from_db_exists(app_context, db_session):
    """Test removing an existing task."""
    upsert_task(
        task_id="task123",
        task_name="Test Task",
        branch_name="feature/test-branch",
    )
    
    result = remove_task_from_db("task123")
    assert result is True
    
    task = get_task_by_id("task123")
    assert task is None


def test_remove_task_from_db_not_exists(app_context, db_session):
    """Test removing a non-existent task."""
    result = remove_task_from_db("nonexistent")
    assert result is False
