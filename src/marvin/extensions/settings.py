from typing import Any, Callable, Literal

from pydantic_settings import BaseSettings

from marvin.extensions.storage.base import (
    BaseAgentStorage,
    BaseChatStore,
    BaseDataSourceStorage,
    BaseRunStorage,
    BaseThreadStore,
)
from marvin.extensions.storage.cache import cache
from marvin.extensions.storage.file_storage.local_file_storage import BaseFileStorage, LocalFileStorage
from marvin.extensions.storage.stores import (
    AgentStore,
    ChatStore,
    DataSourceStore,
    RunStore,
    ThreadStore,
)
from marvin.extensions.utilities.transport import (
    BaseConnectionManager,
    CLIConnectionManager,
)

from .context.base import get_global_state
from asgiref.local import Local


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
    data_source_storage_class: type[BaseDataSourceStorage] = DataSourceStore
    cache: Any = cache


class TransportSettings(BaseSettings):
    channel: Literal["sse", "ws"] = "ws"
    default_manager: Literal["fastapi", "django"] = "fastapi"
    manager: BaseConnectionManager | None = CLIConnectionManager()


class AppContextSettings(BaseSettings):
    container: Callable[[], Local] = get_global_state


class MarvinExtensionsSettings(BaseSettings):
    storage: ExtensionStorageSettings = ExtensionStorageSettings()
    s3: S3Settings = S3Settings()
    default_vector_dimensions: int = 256
    transport: TransportSettings = TransportSettings()
    app_context: AppContextSettings = AppContextSettings()


extension_settings = MarvinExtensionsSettings()


def setup_storage(
    settings: MarvinExtensionsSettings,
    thread_store_class: type[BaseThreadStore] = ThreadStore,
    chat_store_class: type[BaseChatStore] = ChatStore,
    message_store_class: type[BaseChatStore] = ChatStore,
    run_storage_class: type[BaseRunStorage] = RunStore,
    agent_storage_class: type[BaseAgentStorage] = AgentStore,
    data_source_storage_class: type[BaseDataSourceStorage] = DataSourceStore,
) -> MarvinExtensionsSettings:
    settings.storage.thread_store_class = thread_store_class
    settings.storage.chat_store_class = chat_store_class
    settings.storage.message_store_class = message_store_class
    settings.storage.run_storage_class = run_storage_class
    settings.storage.agent_storage_class = agent_storage_class
    settings.storage.data_source_storage_class = data_source_storage_class
    return settings