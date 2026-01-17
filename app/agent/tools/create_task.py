"""Tool for creating implementation tasks."""

import logging

from langchain_core.tools import StructuredTool

from agent.integrations.board_factory import create_board_provider

logger = logging.getLogger(__name__)


def create_task_tool(sys_config: dict, target_list: str) -> StructuredTool:
    """Factory that creates a tool for creating tasks on the configured board."""

    async def create_task(
        title: str,
        instructions: str,
    ) -> str:
        """
        Creates a new task with implementation instructions in the configured list.
        Use this when the user requests to create a task for implementing the analysis findings.

        Args:
            title: A concise title for the implementation task.
            instructions: Detailed implementation instructions based on the analysis.

        Returns:
            Confirmation message with the task URL.
        """
        try:
            if not target_list:
                return "Error: target list not configured"

            board_provider = create_board_provider(sys_config)
            task = await board_provider.create_task(
                name=title,
                description=instructions,
                list_name=target_list,
            )

            logger.info(
                "Created implementation task '%s' in list '%s'",
                task.name,
                target_list,
            )

            return (
                f"Successfully created implementation task: '{task.name}'\n"
                f"Task URL: {task.url}\n"
                f"List: {target_list}"
            )

        except ValueError as e:
            logger.error("Failed to create task: %s", str(e))
            return f"Error: {str(e)}"
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Board provider error: %s", str(e))
            return f"Failed to create task: {str(e)}"

    return StructuredTool.from_function(
        coroutine=create_task,
        name="create_task",
        description=(
            "Creates a new task with implementation instructions in the "
            f"'{target_list}' list. Use this when the user requests to create "
            "a task for implementing the analysis findings."
        ),
    )
