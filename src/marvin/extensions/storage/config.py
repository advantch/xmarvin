from pydantic import BaseModel
from marvin.extensions.settings import extension_settings


class StorageConfig(BaseModel):
    file_storage_type: str = extension_settings.storage.file_storage_class.__name__
    chat_store_type: str = extension_settings.storage.chat_store_class.__name__
    thread_store_type: str = extension_settings.storage.thread_store_class.__name__
    run_storage_type: str = extension_settings.storage.run_storage_class.__name__
    agent_storage_type: str = extension_settings.storage.agent_storage_class.__name__
    # Add other configuration options as needed
