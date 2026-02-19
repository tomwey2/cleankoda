import asyncio

from dotenv import load_dotenv

from app.agent.worker import run_agent_cycle
from app.core.config import get_env_settings
from app.core.extensions import db
from app.core.utils import log_and_validate_env, setup_logging
from app.web import create_app
from app.agent.runtime import RuntimeSetting, prepare_runtime

load_dotenv()

DEFAULT_POLLING_INTERVAL_SECONDS = 60


async def main():
    # 1. Logging Setup
    logger = setup_logging()
    logger.info("Starting Agent (Async)...")

    # 2. Env Validierung
    encryption_key = log_and_validate_env(logger, get_env_settings())

    # 3. App Context erstellen (Nötig für DB Zugriff)
    # Wir starten KEINEN Server, wir nutzen app nur als Hülle für die DB
    app = create_app(encryption_key)

    with app.app_context():
        db.create_all()

    async def run_cycle() -> int:
        with app.app_context():
            runtime: RuntimeSetting | None = prepare_runtime()
            if not runtime:
                logger.info("No runtime configured, skipping cycle")
                return DEFAULT_POLLING_INTERVAL_SECONDS
            if not runtime.agent_settings:
                logger.info("Agent settings not found, skipping cycle")
                return DEFAULT_POLLING_INTERVAL_SECONDS
            if not runtime.agent_settings.is_active:
                logger.info("Agent is not active, skipping cycle")
                return runtime.agent_settings.polling_interval_seconds or DEFAULT_POLLING_INTERVAL_SECONDS
            await run_agent_cycle(runtime)
            return runtime.agent_settings.polling_interval_seconds or DEFAULT_POLLING_INTERVAL_SECONDS

    # 4. Der Infinite Loop
    while True:
        try:
            polling_interval = await run_cycle()
        except Exception as e:
            logger.error("Error in main: %s", e, exc_info=True)
            polling_interval = DEFAULT_POLLING_INTERVAL_SECONDS

        await asyncio.sleep(polling_interval)


if __name__ == "__main__":
    asyncio.run(main())
