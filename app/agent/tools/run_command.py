"""Tool for executing commands inside the workbench development container."""

import logging
import traceback

import docker
from docker.errors import APIError, NotFound
from langchain_core.tools import tool

from app.agent.utils import get_workbench

logger = logging.getLogger(__name__)

try:  # docker socket might be unavailable in some environments
    DOCKER_CLIENT = docker.from_env()
except Exception as exc:  # pylint: disable=broad-exception-caught
    logger.warning("No docker connection! %s", exc)
    logger.debug("Docker connection failure stacktrace:\n%s", traceback.format_exc())
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

    try:
        container = DOCKER_CLIENT.containers.get(get_workbench())

        if container.status != "running":
            return (
                f"Error: Container {get_workbench()} is not running "
                f"(Status: {container.status})."
            )

        logger.info("Executing in workbench: %s", command)

        exec_result = container.exec_run(command, workdir="/coding-agent-workspace")
        output = exec_result.output.decode("utf-8")
        exit_code = exec_result.exit_code

        logger.debug("--- COMMAND OUTPUT (%s) ---%s\n---", command, output)
        output = _truncate_tool_output(output)

        if exit_code == 0:
            return f"✅ SUCCESS:\n{output}"
        return f"❌ FAILED (Exit Code {exit_code}):\n{output}"

    except NotFound:
        logger.error("Container not found: %s", get_workbench())
        logger.debug("Container not found stacktrace:\n%s", traceback.format_exc())
        return (
            f"Error: Container '{get_workbench()}' not found. "
            "Please start the docker-compose setup."
        )
    except APIError:
        logger.error("Docker API error occurred")
        logger.debug("Docker API error stacktrace:\n%s", traceback.format_exc())
        return "Docker API Error occurred"
    except Exception as err:  # pylint: disable=broad-exception-caught
        logger.error("Unexpected system error in run_command: %s", err)
        logger.debug("System error stacktrace:\n%s", traceback.format_exc())
        return f"System Error: {err}"
