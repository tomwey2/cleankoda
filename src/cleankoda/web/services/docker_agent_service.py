"""Docker Agent Service"""

import logging

import docker

logger = logging.getLogger(__name__)

CONTAINER_NAME = "cleankoda-worker"


async def start_docker_agent():
    """Starts the docker agent if it's not already running."""
    client = docker.from_env()

    try:
        client.containers.get(CONTAINER_NAME)
        logger.info("Agent already running.")
        return
    except docker.errors.NotFound:
        pass  # Container doesn't exist, we can start it

    client.containers.run(
        image="cleankoda-agent-java:latest",
        name=CONTAINER_NAME,
        detach=True,
        remove=True,  # Destroys the container automatically when stopped
    )
    logger.info("Agent successfully started.")
    return


async def stop_docker_agent():
    """Stops the docker agent."""
    client = docker.from_env()
    try:
        container = client.containers.get(CONTAINER_NAME)
        container.stop()  # Dies triggert gleichzeitig das 'remove=True'
        logger.info("Agent successfully stopped.")
        return
    except docker.errors.NotFound:
        logger.info("No active agent found.")
        return
