from typing import Any, Literal

from marvin.extensions.storage.base import (
    BaseAgentStorage,
    BaseChatStore,
    BaseRunStorage,
    BaseThreadStore,
)

from marvin.extensions.storage.cache import cache
from marvin.extensions.storage.file_storage import LocalFileStorage, BaseFileStorage
from marvin.extensions.storage.stores import (
    AgentStore,
    ChatStore,
    RunStore,
    ThreadStore,
)
from marvin.extensions.utilities.transport import (
    BaseConnectionManager,
    CLIConnectionManager,
)
from pydantic_settings import BaseSettings


class S3Settings(BaseSettings):
    """
    Default settings for S3 storage.
    """

    bucket_name: str = "marvin-storage"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_endpoint_url_s3: str = ""
    aws_region: str = ""


class ExtensionStorageSettings(BaseSettings):
    chat_store_class: type[BaseChatStore] = ChatStore
    thread_store_class: type[BaseThreadStore] = ThreadStore
    message_store_class: type[BaseChatStore] = ChatStore
    file_storage_class: type[BaseFileStorage] = LocalFileStorage
    run_storage_class: type[BaseRunStorage] = RunStore
    agent_storage_class: type[BaseAgentStorage] = AgentStore
    cache: Any = cache


class TransportSettings(BaseSettings):
    channel: Literal["sse", "ws"] = "ws"
    default_manager: Literal["fastapi", "django"] = "fastapi"
    manager: BaseConnectionManager | None = CLIConnectionManager()


class MarvinExtensionsSettings(BaseSettings):
    storage: ExtensionStorageSettings = ExtensionStorageSettings()
    s3: S3Settings = S3Settings()
    default_vector_dimensions: int = 256
    transport: TransportSettings = TransportSettings()


extension_settings = MarvinExtensionsSettings()
