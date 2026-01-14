"""Create a checkout node"""

from typing import Any, Dict

from agent.state import AgentState


def create_checkout_node():
    """Create a checkout node"""

    async def checkout_node(state: AgentState) -> Dict[str, Any]:  # pylint: disable=unused-argument
        # implement checkout node
        return {}

    return checkout_node
