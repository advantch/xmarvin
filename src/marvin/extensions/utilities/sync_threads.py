from typing import List, Optional
from marvin.beta.assistants import Thread as RemoteThread
from marvin.beta.local.thread import LocalThread
from marvin.extensions.storage.base import BaseThreadStore
from marvin.utilities.openai import get_openai_client
from marvin.extensions.utilities.logging import logger

class ThreadSynchronizer:
    """
    Synchronize remote and local threads.
    This works with references only not actual files.
    Files need to be already available in a file store.
    """
    def __init__(self, local_thread: LocalThread, remote_thread: RemoteThread):
        self.local_thread = local_thread
        self.remote_thread = remote_thread
        self.thread_store = local_thread.thread_storage
        self.client = get_openai_client()

    async def sync_files(self):
        """Synchronize files between local and remote threads."""
        local_files = await self.local_thread.list_files_async()
        remote_files = await self.remote_thread.list_files_async()

        files_to_add = set(local_files) - set(remote_files)
        files_to_remove = set(remote_files) - set(local_files)
        if not files_to_add and not files_to_remove:
            logger.debug(f"No files to add or remove for thread {self.local_thread.id}")
            return

        await self._add_files_to_remote(files_to_add)
        await self._remove_files_from_remote(files_to_remove)

    async def sync_vector_store(self):
        """Synchronize vector store between local and remote threads."""
        local_has_vector_store = await self.local_thread.has_vector_store_async()
        remote_has_vector_store = await self.remote_thread.has_vector_store_async()

        if local_has_vector_store and not remote_has_vector_store:
            await self._create_remote_vector_store()
        elif not local_has_vector_store and remote_has_vector_store:
            await self._remove_remote_vector_store()

    async def _add_files_to_remote(self, files: List[str]):
        """Add files to the remote thread."""
        for file_path in files:
            with open(file_path, "rb") as file:
                uploaded_file = await self.client.files.create(file=file, purpose="assistants")
                await self.remote_thread.add_async(
                    message="",
                    file_search_files=[uploaded_file.id]
                )
        logger.info(f"Added {len(files)} files to remote thread {self.remote_thread.id}")

    async def _remove_files_from_remote(self, files: List[str]):
        """Remove files from the remote thread."""
        remote_files = await self.client.beta.threads.files.list(thread_id=self.remote_thread.id)
        for file in remote_files.data:
            if file.filename in files:
                await self.client.beta.threads.files.delete(thread_id=self.remote_thread.id, file_id=file.id)
        logger.info(f"Removed {len(files)} files from remote thread {self.remote_thread.id}")

    async def _create_remote_vector_store(self):
        """Create a vector store for the remote thread."""
        vector_store_id = await self.remote_thread.create_vector_store_async("Thread Vector Store")
        await self.remote_thread.add_vector_store_async(vector_store_id)
        logger.info(f"Created vector store for remote thread {self.remote_thread.id}")

    async def _remove_remote_vector_store(self):
        """Remove the vector store from the remote thread."""
        await self.remote_thread.remove_vector_store_async()
        logger.info(f"Removed vector store from remote thread {self.remote_thread.id}")

async def sync_thread(local_thread: LocalThread, remote_thread: RemoteThread):
    """Synchronize a local thread with its remote counterpart."""
    synchronizer = ThreadSynchronizer(local_thread, remote_thread)
    await synchronizer.sync_files()
    await synchronizer.sync_vector_store()

    if not local_thread.external_id:
        local_thread.external_id = remote_thread.id
        local_thread.thread_storage.update(local_thread)

    logger.info(f"Synchronized thread {local_thread.id} with remote thread {remote_thread.id}")