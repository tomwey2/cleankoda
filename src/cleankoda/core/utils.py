"""Utility functions for the application."""

import json
import logging
import logging.config
import os
from pathlib import Path
from typing import Any


def setup_logging(
    config_file_path: Path | None = None,
) -> logging.Logger:
    """
    Setup logging for the application.

    This function configures logging for the application. It can load a configuration
    from a json or ini style file if provided, or use a default configuration.
    """

    config_path: Path | None = config_file_path
    if config_path is None:
        env_config = os.environ.get("LOGGING_CONFIG_FILE")
        if env_config:
            config_path = Path(env_config)

    if config_path:
        if config_path.exists():
            suffix = config_path.suffix.lower()
            if suffix == ".json":
                with config_path.open("r", encoding="utf-8") as config_file_handle:
                    config_data: dict[str, Any] = json.load(config_file_handle)
                config_data.setdefault("disable_existing_loggers", False)
                _ensure_log_handler_directories(config_data)
                logging.config.dictConfig(config_data)
            else:
                logging.config.fileConfig(config_path, disable_existing_loggers=False)
            return logging.getLogger("entrypoint")

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(name)s - %(levelname)s - %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "standard",
            },
        },
        "root": {
            "level": "DEBUG",
            "handlers": ["console"],
        },
        "loggers": {
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            "werkzeug": {"level": "WARNING"},
        },
    }

    logging.config.dictConfig(logging_config)

    logger = logging.getLogger("entrypoint")
    if config_path:
        logger.warning(
            "Logging config file '%s' not found. Falling back to built-in defaults.",
            config_path,
        )
    return logger


def _ensure_log_handler_directories(config_data: dict[str, Any]) -> None:
    """Create directories required by file-based log handlers."""

    handlers = config_data.get("handlers", {})
    for handler_name, handler_config in handlers.items():
        filename = handler_config.get("filename")
        if not filename:
            continue
        path = Path(filename).expanduser()
        parent = path.parent
        if parent.exists() or str(parent) == ".":
            continue
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise OSError(
                f"Failed to create log directory for handler '{handler_name}': {error}"
            ) from error


def mask_secret(value: str) -> str:
    """Mask a secret value for logging."""
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    head = value[:2]
    tail = value[-2:]
    return f"{head}{'*' * (len(value) - 4)}{tail}"
