from marvin.extensions.storage.config import StorageConfig
from marvin.extensions.storage.base import BaseFileStorage, BaseChatStore, BaseThreadStore, BaseRunStorage, BaseAgentStorage
from marvin.extensions.storage.file_storage import LocalFileStorage
from marvin.extensions.storage.memory_store import MemoryChatStore, MemoryThreadStore, MemoryRunStore, MemoryAgentStore
# Import other storage implementations as needed

class StorageFactory:
    @staticmethod
    def create_file_storage(config: StorageConfig) -> BaseFileStorage:
        if config.file_storage_type == "LocalFileStorage":
            return LocalFileStorage()
        # Add other file storage types as needed
        raise ValueError(f"Unsupported file storage type: {config.file_storage_type}")

    @staticmethod
    def create_chat_store(config: StorageConfig) -> BaseChatStore:
        if config.chat_store_type == "MemoryChatStore":
            return MemoryChatStore()
        # Add other chat store types as needed
        raise ValueError(f"Unsupported chat store type: {config.chat_store_type}")

    @staticmethod
    def create_thread_store(config: StorageConfig) -> BaseThreadStore:
        if config.thread_store_type == "MemoryThreadStore":
            return MemoryThreadStore()
        # Add other thread store types as needed
        raise ValueError(f"Unsupported thread store type: {config.thread_store_type}")

    @staticmethod
    def create_run_storage(config: StorageConfig) -> BaseRunStorage:
        if config.run_storage_type == "MemoryRunStore":
            return MemoryRunStore()
        # Add other run storage types as needed
        raise ValueError(f"Unsupported run storage type: {config.run_storage_type}")

    @staticmethod
    def create_agent_storage(config: StorageConfig) -> BaseAgentStorage:
        if config.agent_storage_type == "MemoryAgentStore":
            return MemoryAgentStore()
        # Add other agent storage types as needed
        raise ValueError(f"Unsupported agent storage type: {config.agent_storage_type}")