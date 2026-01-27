"""Tool for executing commands inside the workbench development container."""

import logging
import os

import docker
from docker.errors import APIError, NotFound
from langchain_core.tools import tool

from app.agent.utils import get_codespace, get_workbench

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


@tool
# pylint: disable=too-many-return-statements
def run_command(command: str) -> str:
    """Execute a shell command inside the workbench container."""
    if not DOCKER_CLIENT:
        return "Error: Docker client not initialized. Is the socket mounted?"

    container_name = os.environ.get("WORKBENCH_CONTAINER_NAME", get_workbench())
    workbench_workdir = os.environ.get("WORKBENCH_CODESPACE", get_codespace())
    try:        
        container = DOCKER_CLIENT.containers.get(container_name)

        if container.status != "running":
            return (
                f"Error: Container {container_name} is not running "
                f"(Status: {container.status})."
            )

        logger.info("Executing in %s: %s", container_name, command)

        exec_result = container.exec_run(command, workdir=workbench_workdir)
        output = exec_result.output.decode("utf-8")
        exit_code = exec_result.exit_code

        logger.debug("--- COMMAND OUTPUT (%s) ---%s\n---", command, output)
        output = _truncate_tool_output(output)

        if exit_code == 0:
            return f"✅ SUCCESS:\n{output}"
        return f"❌ FAILED (Exit Code {exit_code}):\n{output}"

    except NotFound:
        return (
            f"Error: Container '{container_name}' not found. "
            "Please start the docker-compose setup."
        )
    except APIError as api_exc:
        return f"Docker API Error: {api_exc}"
    except Exception as err:  # pylint: disable=broad-exception-caught
        return f"System Error: {err}"
