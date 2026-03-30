import asyncio
import sys

from dotenv import load_dotenv

from app.agent.worker import run_agent_cycle
from app.core.config import get_env_settings
from app.core.extensions import db
from app.core.utils import log_and_validate_env, setup_logging
from app.web import create_app
from app.agent.runtime import RuntimeSetting, prepare_runtime


DEFAULT_POLLING_INTERVAL_SECONDS = 60


async def main():
    # 1. Logging Setup
    logger = setup_logging()
    logger.info("Starting Agent (Async)...")

    env_settings = get_env_settings()
    # 2. Env Validierung
    encryption_key = log_and_validate_env(logger, env_settings)

    # 3. App Context erstellen (Nötig für DB Zugriff)
    # Wir starten KEINEN Server, wir nutzen app nur als Hülle für die DB
    app = create_app(encryption_key)

    with app.app_context():
        # TODO: good for local dev, but not for production. Must be changed for production.
        db.create_all()

    deployment_mode = env_settings.deployment_mode

    # ----- SERVERLESS MODE IN GCP RUN -----
    if deployment_mode == "SERVERLESS":
        logger.info("Agent is running in SERVERLESS mode")
        try:
            await run_cycle(app, logger)
        except Exception as e:
            logger.error("Error in main: %s", e, exc_info=True)

        logger.info("Agent stopped")
        sys.exit(0)

    # ----- ON PREMISE MODE (LOCAL OR ON SERVER) -----
    if deployment_mode == "ON_PREMISE":
        logger.info("Agent is running in ON_PREMISE mode, endless loop")
        while True:
            try:
                polling_interval = await run_cycle(app, logger)
            except Exception as e:
                logger.error("Error in main: %s", e, exc_info=True)
                polling_interval = DEFAULT_POLLING_INTERVAL_SECONDS

            await asyncio.sleep(polling_interval)

    # ----- UNKNOWN MODE -----
    logger.error("Agent has unknown deployment mode: %s", deployment_mode)
    sys.exit(1)


async def run_cycle(app, logger) -> int:
    with app.app_context():
        runtime: RuntimeSetting | None = prepare_runtime()

        if not runtime or not runtime.agent_settings:
            logger.info("No runtime or agent settings found, skipping cycle")
            return DEFAULT_POLLING_INTERVAL_SECONDS

        if not runtime.agent_settings.is_active:
            logger.info("Agent is not active, skipping cycle")
        else:
            await run_agent_cycle(runtime)

        return runtime.agent_settings.polling_interval_seconds or DEFAULT_POLLING_INTERVAL_SECONDS


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
