from marvin.extensions.storage.base import (
    BaseAgentStorage,
    BaseChatStore,
    BaseFileStorage,
    BaseRunStorage,
    BaseThreadStore,
)
from marvin.extensions.storage.config import StorageConfig
from marvin.extensions.storage.factory import StorageFactory


class GlobalStorage:
    _file_instance: BaseFileStorage = None
    _chat_instance: BaseChatStore = None
    _thread_instance: BaseThreadStore = None
    _run_instance: BaseRunStorage = None
    _agent_instance: BaseAgentStorage = None

    @classmethod
    def get_file_storage(cls) -> BaseFileStorage:
        if cls._file_instance is None:
            config = StorageConfig()
            cls._file_instance = StorageFactory.create_file_storage(config)
        return cls._file_instance

    @classmethod
    def get_chat_store(cls) -> BaseChatStore:
        if cls._chat_instance is None:
            config = StorageConfig()
            cls._chat_instance = StorageFactory.create_chat_store(config)
        return cls._chat_instance

    @classmethod
    def get_thread_store(cls) -> BaseThreadStore:
        if cls._thread_instance is None:
            config = StorageConfig()
            cls._thread_instance = StorageFactory.create_thread_store(config)
        return cls._thread_instance

    @classmethod
    def get_run_storage(cls) -> BaseRunStorage:
        if cls._run_instance is None:
            config = StorageConfig()
            cls._run_instance = StorageFactory.create_run_storage(config)
        return cls._run_instance

    @classmethod
    def get_agent_storage(cls) -> BaseAgentStorage:
        if cls._agent_instance is None:
            config = StorageConfig()
            cls._agent_instance = StorageFactory.create_agent_storage(config)
        return cls._agent_instance

    @classmethod
    def set_file_storage(cls, storage: BaseFileStorage):
        cls._file_instance = storage

    @classmethod
    def set_chat_store(cls, store: BaseChatStore):
        cls._chat_instance = store

    @classmethod
    def set_thread_store(cls, store: BaseThreadStore):
        cls._thread_instance = store

    @classmethod
    def set_run_storage(cls, storage: BaseRunStorage):
        cls._run_instance = storage

    @classmethod
    def set_agent_storage(cls, storage: BaseAgentStorage):
        cls._agent_instance = storage


def get_file_storage() -> BaseFileStorage:
    return GlobalStorage.get_file_storage()


def get_chat_store() -> BaseChatStore:
    return GlobalStorage.get_chat_store()


def get_thread_store() -> BaseThreadStore:
    return GlobalStorage.get_thread_store()


def get_run_storage() -> BaseRunStorage:
    return GlobalStorage.get_run_storage()


def get_agent_storage() -> BaseAgentStorage:
    return GlobalStorage.get_agent_storage()
