"""
Abstract interface for board system integrations.

This module defines the contract that all board providers (Trello, GitHub, Jira, etc.)
must implement. It provides domain models that are independent of any specific
board system implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BoardTask:
    """
    Domain model for a task, independent of the board system.
    
    Attributes:
        id: Unique identifier for the task
        name: Title/name of the task
        description: Detailed description of the task
        list_id: ID of the list/column containing this task
        list_name: Name of the list/column containing this task
        url: URL to view the task in the board system
    """
    id: str
    name: str
    description: str
    list_id: str
    list_name: str
    url: str = ""


@dataclass
class BoardComment:
    """
    Domain model for a comment on a task.
    
    Attributes:
        id: Unique identifier for the comment
        text: Content of the comment
        author: Name of the comment author
        date: Timestamp when the comment was created
    """
    id: str
    text: str
    author: str
    date: datetime


@dataclass
class BoardListMove:
    """
    Domain model for tracking when a task moves between lists.
    
    Attributes:
        id: Unique identifier for the move action
        date: Timestamp when the move occurred
        list_before: Name of the list before the move
        list_after: Name of the list after the move
    """
    id: str
    date: datetime
    list_before: str | None
    list_after: str | None


class BoardProvider(ABC):
    """
    Abstract interface for board system operations.
    
    All board providers (Trello, GitHub Projects, Jira, etc.) must implement
    this interface to ensure consistent behavior across different systems.
    """

    @abstractmethod
    async def get_lists(self) -> list[dict]:
        """
        Fetch all lists/columns from the board.
        
        Returns:
            List of dictionaries with 'id' and 'name' keys
        """

    @abstractmethod
    async def get_tasks_from_list(self, list_id: str) -> list[BoardTask]:
        """
        Fetch all tasks from a specific list.
        
        Args:
            list_id: The ID of the list to fetch tasks from
            
        Returns:
            List of BoardTask objects
        """

    @abstractmethod
    async def move_task_to_list(self, task_id: str, list_id: str) -> None:
        """
        Move a task to a different list.
        
        Args:
            task_id: The ID of the task to move
            list_id: The ID of the target list
            
        Raises:
            RuntimeError: If the move operation fails
        """

    @abstractmethod
    async def move_task_to_named_list(self, task_id: str, list_name: str) -> str:
        """
        Move a task to a list identified by name.
        
        Args:
            task_id: The ID of the task to move
            list_name: The name of the target list
            
        Returns:
            The ID of the target list
            
        Raises:
            ValueError: If the list name is not found
            RuntimeError: If the move operation fails
        """

    @abstractmethod
    async def add_comment(self, task_id: str, comment: str) -> None:
        """
        Add a comment to a task.
        
        Args:
            task_id: The ID of the task
            comment: The comment text to add
            
        Raises:
            RuntimeError: If adding the comment fails
        """

    @abstractmethod
    async def get_comments(self, task_id: str) -> list[BoardComment]:
        """
        Fetch all comments for a task.
        
        Args:
            task_id: The ID of the task
            
        Returns:
            List of BoardComment objects
            
        Raises:
            RuntimeError: If fetching comments fails
        """

    @abstractmethod
    async def get_list_moves(self, task_id: str) -> list[BoardListMove]:
        """
        Fetch the history of list moves for a task.
        
        Args:
            task_id: The ID of the task
            
        Returns:
            List of BoardListMove objects
            
        Raises:
            RuntimeError: If fetching move history fails
        """

    @abstractmethod
    async def create_task(
        self, name: str, description: str, list_name: str
    ) -> BoardTask:
        """
        Create a new task in the specified list.
        
        Args:
            name: The title/name of the task
            description: The description/body of the task
            list_name: The name of the list to create the task in
            
        Returns:
            The created BoardTask object
            
        Raises:
            ValueError: If the list name is not found
            RuntimeError: If task creation fails
        """
