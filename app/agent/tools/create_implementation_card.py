"""Tool for creating implementation cards in Trello."""

import logging

from langchain_core.tools import StructuredTool

from agent.integrations.trello_client import create_trello_card

logger = logging.getLogger(__name__)


def create_implementation_card_tool(sys_config: dict) -> StructuredTool:
    """
    Factory function that creates a tool for creating implementation cards.

    Args:
        sys_config: System configuration to bind to the tool.

    Returns:
        A StructuredTool instance with sys_config bound.
    """

    async def create_implementation_card(
        title: str,
        instructions: str,
    ) -> str:
        """
        Creates a new Trello card with implementation instructions in the configured incoming list.
        Use this when the user requests to create a card for implementing the analysis findings.

        Args:
            title: A concise title for the implementation task.
            instructions: Detailed implementation instructions based on the analysis.

        Returns:
            Confirmation message with the card URL.
        """
        try:
            target_list = sys_config.get("trello_readfrom_list")
            if not target_list:
                return "Error: trello_readfrom_list not configured in sys_config"

            result = await create_trello_card(
                name=title,
                description=instructions,
                list_name=target_list,
                sys_config=sys_config,
            )

            logger.info(
                "Created implementation card '%s' in list '%s'",
                result["name"],
                result["list"],
            )

            return (
                f"Successfully created implementation card: '{result['name']}'\n"
                f"Card URL: {result['url']}\n"
                f"List: {result['list']}"
            )

        except ValueError as e:
            logger.error("Failed to create card: %s", str(e))
            return f"Error: {str(e)}"
        except RuntimeError as e:
            logger.error("Trello API error: %s", str(e))
            return f"Failed to create card: {str(e)}"

    return StructuredTool.from_function(
        coroutine=create_implementation_card,
        name="create_implementation_card",
        description=(
            "Creates a new Trello card with implementation instructions in the "
            "configured incoming list. Use this when the user requests to create "
            "a card for implementing the analysis findings."
        ),
    )
