from typing import Any
from marvin.extensions.storage.base import (
    BaseAgentStorage,
    BaseChatStore,
    BaseFileStorage,
    BaseRunStorage,
    BaseThreadStore,
)
from marvin.extensions.storage.cache import cache
from marvin.extensions.storage.file_storage import SimpleFileStorage
from marvin.extensions.storage.simple_chatstore import (
    SimpleAgentStorage,
    SimpleChatStore,
    SimpleRunStore,
    SimpleThreadStore,
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
    chat_store_class: type[BaseChatStore] = SimpleChatStore
    thread_store_class: type[BaseThreadStore] = SimpleThreadStore
    message_store_class: type[BaseChatStore] = SimpleChatStore
    file_storage_class: type[BaseFileStorage] = SimpleFileStorage
    run_storage_class: type[BaseRunStorage] = SimpleRunStore
    agent_storage_class: type[BaseAgentStorage] = SimpleAgentStorage
    cache: Any = cache


class MarvinExtensionsSettings(BaseSettings):
    storage: ExtensionStorageSettings = ExtensionStorageSettings()
    s3: S3Settings = S3Settings()
    default_vector_dimensions: int = 256


extensions_settings = MarvinExtensionsSettings()
