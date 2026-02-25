"""
Module: utils
Description: App-wide utility functions
"""

from dataclasses import fields
import json
from uuid import UUID
import logging

from typing import Any
import logging.config

from app.settings import settings
from app.typings import LogLevel

logger = logging.getLogger(__name__)


def init_logging(log_level: LogLevel = settings.log_level) -> None:
    config = settings.logging_config.copy()
    config["root"]["level"] = log_level.upper()
    for handler in config["handlers"].values():
        handler["level"] = log_level.upper()
    logging.config.dictConfig(config)


def dict2str(data: dict[str, Any], indent: int = 2) -> str:
    """Convert a dictionary to a nicely formatted string."""
    return json.dumps(data, indent=indent, default=str)


def get_settings_starting_with(prefix: str, remove_prefix: bool = False) -> dict[str, Any]:
    return {
        field.removeprefix(prefix if remove_prefix else ""): value
        for field, value in settings
        if field.startswith(prefix)
    }


def convert_str_fields_to_uuid(x):
    for f in fields(x):
        if f.type == UUID and isinstance(getattr(x, f.name), str):
            setattr(x, f.name, UUID(getattr(x, f.name)))
