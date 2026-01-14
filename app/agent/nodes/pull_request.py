"""Create a pull request node"""

from typing import Any, Dict

from agent.state import AgentState


def create_pull_request_node():
    """Create a pull request node"""

    async def pull_request_node(state: AgentState) -> Dict[str, Any]:  # pylint: disable=unused-argument
        # implement pull request node
        return {}

    return pull_request_node
