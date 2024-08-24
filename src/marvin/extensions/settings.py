from pydantic_settings import BaseSettings
from marvin.extensions.storage.simple_chatstore import SimpleChatStore, SimpleThreadStore, SimpleRunStore, SimpleAgentStorage
from marvin.extensions.storage.file_storage import SimpleFileStorage
from marvin.extensions.storage.cache import cache
from marvin.extensions.storage.base import BaseAgentStorage, BaseChatStore, BaseThreadStore, BaseChatStore, BaseFileStorage, BaseRunStorage

class ExtensionStorageSettings(BaseSettings):
    chat_store_class: type[BaseChatStore] = SimpleChatStore
    thread_store_class: type[BaseThreadStore] = SimpleThreadStore
    message_store_class: type[BaseChatStore] = SimpleChatStore
    file_storage_class: type[BaseFileStorage] = SimpleFileStorage
    run_storage_class: type[BaseRunStorage] = SimpleRunStore
    agent_storage_class: type[BaseAgentStorage] = SimpleAgentStorage
    cache = cache


class MarvinExtensionsSettings(BaseSettings):
    storage: ExtensionStorageSettings = ExtensionStorageSettings()


extensions_settings = MarvinExtensionsSettings()