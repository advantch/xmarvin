import os
from pathlib import Path
from typing import Any, Callable, Literal, Union

import litellm
from asgiref.local import Local
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from marvin.extensions.utilities.transport import (
    BaseConnectionManager,
    CLIConnectionManager,
)
from marvin.settings import settings as marvin_settings

from .context.base import get_global_state


class S3Settings(BaseSettings):
    """
    Settings for S3 storage.
    """

    bucket_name: str = "marvin-storage"
    access_key_id: str = ""
    secret_access_key: str = ""
    endpoint_url: str = ""
    region: str = ""

    model_config = SettingsConfigDict(env_prefix="MARVIN_S3_")


class TransportSettings(BaseSettings):
    channel: Literal["sse", "ws"] = "ws"
    default_manager: Literal["fastapi", "django"] = "fastapi"
    manager: BaseConnectionManager | None = CLIConnectionManager()


class AppContextSettings(BaseSettings):
    container: Callable[[], Local] = get_global_state
    get_default_db_url: Callable[[], str] = lambda: "sqlite:///:memory:"


class MarvinExtensionsSettings(BaseSettings):
    home_path: Path = litellm.Field(
        default="~/.marvin_extensions",
        description="The path to the Marvin Extensions home directory.",
        validate_default=True,
    )
    default_vector_dimensions: int = 256
    transport: TransportSettings = TransportSettings()
    global_context: AppContextSettings = AppContextSettings()

    def __setattr__(self, name: str, value: Any) -> None:
        # wrap bare strings in SecretStr if the field is annotated with SecretStr
        field = self.model_fields.get(name)
        if field:
            annotation = field.annotation
            base_types = (
                getattr(annotation, "__args__", None)
                if getattr(annotation, "__origin__", None) is Union
                else (annotation,)
            )
            if SecretStr in base_types and not isinstance(value, SecretStr):  # type: ignore # noqa: E501
                value = SecretStr(value)
        super().__setattr__(name, value)


# global settings
extension_settings = MarvinExtensionsSettings()
s3_settings = S3Settings()


def update_marvin_settings(api_key: str | None = None):
    if api_key:
        marvin_settings.openai.api_key = api_key
    else:
        marvin_settings.openai.api_key = os.getenv("OPENAI_API_KEY")


def update_litellm_settings(api_key: str | None = None):
    if api_key:
        litellm.openai.api_key = api_key
    else:
        litellm.openai.api_key = marvin_settings.openai.api_key
    # update anthropic api key
    litellm.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    litellm.cohere_key = os.getenv("COHERE_API_KEY")
