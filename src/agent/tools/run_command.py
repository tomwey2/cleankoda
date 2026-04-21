"""Tool for executing commands inside the workbench development container."""

import logging

import docker
from docker.errors import APIError, NotFound
from langchain_core.tools import tool

from src.agent.utils import get_workbench, get_workspace, get_workbench_workspace


logger = logging.getLogger(__name__)

try:  # docker socket might be unavailable in some environments
    DOCKER_CLIENT = docker.from_env()
except Exception as exc:  # pylint: disable=broad-exception-caught
    logger.warning("No docker connection! %s", exc)
    DOCKER_CLIENT = None

MAX_TOOL_OUTPUT_CHARS = 20000


def _truncate_tool_output(output: str, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """Truncate long command output while keeping the start and end."""
    if len(output) <= limit:
        return output

    half = limit // 2
    return (
        output[:half]
        + "\n... [output truncated to stay within prompt budget] ...\n"
        + output[-half:]
    )


def _translate_workspace_path(command: str) -> str:
    """Translate agent workspace paths to container workspace paths.

    The LLM may generate commands with agent workspace paths (e.g.,
    /home/user/.local/workspace) but these need to be translated to
    container paths (/coding-agent-workspace) for execution.

    Args:
        command: The command string potentially containing host paths

    Returns:
        Command with host workspace paths replaced by container paths
    """
    agent_workspace = get_workspace()
    workbench_workspace = get_workbench_workspace()

    # Replace host workspace path with container workspace path
    if agent_workspace in command:
        translated = command.replace(agent_workspace, workbench_workspace)
        logger.debug(
            "Translated workspace path: %s -> %s",
            agent_workspace,
            workbench_workspace
        )
        return translated

    return command


@tool
# pylint: disable=too-many-return-statements
def run_command(command: str) -> str:
    """Execute a shell command inside the workbench container."""
    if not DOCKER_CLIENT:
        return "Error: Docker client not initialized. Is the socket mounted?"

    try:
        container = DOCKER_CLIENT.containers.get(get_workbench())

        if container.status != "running":
            return (
                f"Error: Container {get_workbench()} is not running "
                f"(Status: {container.status})."
            )

        # Translate any host workspace paths to container paths
        translated_command = _translate_workspace_path(command)

        logger.info("Executing in workbench: %s", translated_command)

        exec_result = container.exec_run(
            ["bash", "-lc", translated_command],
            workdir="/coding-agent-workspace",
        )
        output = exec_result.output.decode("utf-8")
        exit_code = exec_result.exit_code

        logger.debug("--- COMMAND OUTPUT (%s) ---%s\n---", command, output)
        output = _truncate_tool_output(output)

        if exit_code == 0:
            return f"✅ SUCCESS:\n{output}"
        return f"❌ FAILED (Exit Code {exit_code}):\n{output}"

    except NotFound:
        return (
            f"Error: Container '{get_workbench()}' not found. "
            "Please start the docker-compose setup."
        )
    except APIError as api_exc:
        return f"Docker API Error: {api_exc}"
    except Exception as err:  # pylint: disable=broad-exception-caught
        return f"System Error: {err}"
