"""
Module: settings
Description: Contains configuration settings and environment variables used in the /app directory.
Architecture:
- Defines Pydantic settings object(s) from pydantic.BaseSettings
- exposes the settings as a singleton instance for import: `settings = Settings()`
Decision points:
- Should env variables be touched here?
- Multiple settings objects for different pieces? Different environments (prod, dev)?
"""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict
from app.typings import LogLevel


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")
    # LLM settings
    ollama_url: str = (
        "http://localhost:11434"  # "http://ollama:11434" # <- endpoint for DockerGPU; "http://localhost:11434" <- local Ollama endpoint
    )
    concept_extraction_model_name: str = "mistral-small3.2:latest"
    concept_extraction_temperature: float = 0.3
    definition_generation_model_name: str = "mistral-small3.2:latest"
    definition_generation_temperature: float = 0.3
    instructor_max_retries: int = 3  # default max retries for LLM requests

    @property
    def available_models(self) -> set[str]:
        """List of available LLM models."""
        available_models = {
            "mistral-small3.2:latest",
        }
        available_models.add(self.model_name)
        return available_models

    # Server settings
    host: str = "0.0.0.0"
    port: int = 5008
    reload: bool = True  # enable auto-reload (dev)
    httpx_timeout: int = 30  # timeout for httpx requests

    # DBs settings
    # Chroma - Concepts' embeddings
    chroma_database: str = "./data/chroma_db"
    chroma_embedding_model_name: str = "nomic-embed-text:latest"
    chroma_anonymized_telemetry: bool = False  # https://github.com/open-webui/open-webui/discussions/15624
    # SQLite - Chunks, Concepts & Taxonomies
    sqlite_database: str = "file:data/store.db"
    sqlite_uri: bool = True

    @property
    def api_url(self) -> str:
        """Full API URL for the application."""
        display_host = "localhost" if self.host == "0.0.0.0" else self.host
        return f"http://{display_host}:{self.port}"

    # Logging settings
    log_level: LogLevel = "DEBUG"
    dependency_log_level: LogLevel = "WARNING"

    @property
    def logging_config(self) -> dict:
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": self.log_level,
                },
            },
            "root": {
                "handlers": ["console"],
                "level": self.log_level,
            },
            "loggers": {
                "asyncio": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
                "chromadb": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
                "httpcore": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
                "httpx": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
                "instructor": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
                "openai": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
                "pdfminer": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
                "python_multipart": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
                "urllib3": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
                "unstructured": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
                "uvicorn": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
                "watchfiles": {
                    "handlers": ["console"],
                    "level": self.dependency_log_level,
                    "propagate": False,
                },
            },
        }


def reset_settings(**overrides):
    """Overrides default settings. Designed for use in notebooks."""
    # Clear existing overrides
    keys_to_remove = [key for key in os.environ.keys() if key.startswith("APP_")]
    for key in keys_to_remove:
        print(f"Removing existing env var: {key}")
        del os.environ[key]

    # Set new overrides
    for key, value in overrides.items():
        env_key = f"APP_{key.upper()}"
        os.environ[env_key] = str(value)

    global settings
    settings = Settings()


settings = Settings()
