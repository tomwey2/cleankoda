"""Tool for executing commands inside the Java development container."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.tools._base import (
    APIError,
    DOCKER_CLIENT,
    NotFound,
    get_workbench,
    get_workspace,
    logger,
    truncate_tool_output,
)


@tool
def run_java_command(command: str) -> str:
    """Execute a shell command inside the Java container."""
    if not DOCKER_CLIENT:
        return "Error: Docker client not initialized. Is the socket mounted?"

    try:
        container = DOCKER_CLIENT.containers.get(get_workbench())

        if container.status != "running":
            return (
                f"Error: Container {get_workbench()} is not running "
                f"(Status: {container.status})."
            )

        logger.info("Executing in Java-Box: %s", command)

        exec_result = container.exec_run(command, workdir=get_workspace())
        output = exec_result.output.decode("utf-8")
        exit_code = exec_result.exit_code

        logger.debug("--- COMMAND OUTPUT (%s) ---%s\n---", command, output)
        output = truncate_tool_output(output)

        if exit_code == 0:
            return f"✅ SUCCESS:\n{output}"
        return f"❌ FAILED (Exit Code {exit_code}):\n{output}"

    except NotFound:
        return (
            f"Error: Container '{get_workbench()}' not found. "
            "Please start the docker-compose setup."
        )
    except APIError as exc:
        return f"Docker API Error: {exc}"
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return f"System Error: {exc}"
