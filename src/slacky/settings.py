from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, model_validator
from pydantic_ai.models import KnownModelName
from pydantic_settings import BaseSettings, SettingsConfigDict
from raggy.vectorstores.chroma import ChromaClientType
from typing_extensions import Self

from slacky.logging import setup_logging

DEFAULT_BASE_SYSTEM_PROMPT_PATH = Path("~/.slacky/base_system_prompt.txt").expanduser()
MESSAGE_CACHE = Path("~/.slacky/message_cache.json").expanduser()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SLACKY_",
        env_file=".env",
        extra="ignore",
    )
    ai_model: KnownModelName = Field(
        default="openai:gpt-4o", description="AI model to use"
    )
    ai_temperature: float = Field(default=0.7, description="AI temperature to use")

    base_system_prompt_path: Path = Field(
        default=DEFAULT_BASE_SYSTEM_PROMPT_PATH,
        description="Path to base system prompt file",
    )
    base_system_prompt: str = Field(
        default=..., description="Base system prompt to use"
    )

    message_cache_path: Path = Field(
        default=MESSAGE_CACHE,
        description="Path to message cache file",
    )
    host: str = Field(default="0.0.0.0", description="Host to run the server on")
    port: int = Field(default=8000, description="Port to run the server on")

    log_level: str = Field(default="INFO", description="Logging level")

    bot_token: SecretStr = Field(
        default=..., description="Slack Bot User OAuth Token - starts with 'xoxb-'"
    )
    signing_secret: SecretStr = Field(
        default=..., description="Slack Signing Secret - used to verify requests"
    )

    google_api_key: SecretStr = Field(default=..., description="Google API Key")
    google_cx: SecretStr = Field(
        default=..., description="Google Custom Search Engine ID"
    )

    namespace: str = Field(default="slacky", description="Namespace to use")
    chroma_client_type: ChromaClientType = Field(
        default="base", description="Chroma client type"
    )

    notification_channel_id: str = Field(
        default=..., description="Channel ID to send notifications to"
    )
    # Development
    debug: bool = Field(default=False, description="Enable debug mode")

    @model_validator(mode="before")
    @classmethod
    def setup_defaults(cls: type[Self], values: dict[str, Any]) -> dict[str, Any]:
        base_system_prompt_path = Path(
            values.get("base_system_prompt_path", DEFAULT_BASE_SYSTEM_PROMPT_PATH)
        )
        assert (
            base_system_prompt_path is not None
        ), "base_system_prompt_path is required"
        if not base_system_prompt_path.exists():
            base_system_prompt_path.touch()
            base_system_prompt_path.write_text(
                "You are a helpful and friendly Slack assistant. "
                "Use your memory of conversation threads and tools "
                "to answer questions and help the user."
            )
        if not values.get("base_system_prompt"):
            values["base_system_prompt"] = base_system_prompt_path.read_text()
        if not values.get("message_cache_path"):
            values["message_cache_path"] = MESSAGE_CACHE
        if (cache_path := values.get("message_cache_path")) and not cache_path.exists():
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.touch()
        return values

    @model_validator(mode="after")
    def ensure_logging_setup(self: Self) -> Self:
        level = "DEBUG" if self.debug else self.log_level
        setup_logging(level=level)
        return self

    @model_validator(mode="after")
    def log_settings(self: Self) -> Self:
        from slacky.logging import get_logger

        logger = get_logger(__name__)
        logger.debug(f"Settings: {self.model_dump_json(indent=2)}")
        return self


settings = Settings()
