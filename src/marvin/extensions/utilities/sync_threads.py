from typing import List

from marvin.beta.assistants import Thread as RemoteThread
from marvin.extensions.context.run_context import get_current_run
from marvin.extensions.storage.data_source_store import (
    BaseDataSourceStore,
    InMemoryDataSourceStore,
)
from marvin.extensions.utilities.logging import logger


async def sync_files_to_remote_thread(local_thread, remote_thread):
    """
    Synchronize files between local and remote threads.
    """
    local_files = await local_thread.get_files_async()
    for _, file in local_files:
        await remote_thread.add_files_to_vector_store_async([file])


async def add_files_to_remote_async(
    files: List[str],
    remote_thread: RemoteThread,
    data_source_store: BaseDataSourceStore | None = None,
):
    """Add files to the remote thread."""
    if not files:
        return
    ctx = get_current_run()
    if ctx:
        data_source_store = ctx.stores.data_source_store
    else:
        data_source_store = data_source_store or InMemoryDataSourceStore()

    data_sources = await data_source_store.list_async()
    for data_source in data_sources:
        if not data_source.file_store_metadata:
            continue

        data_source, file_content = await data_source_store.get_file_async(
            data_source.id
        )
        if not file_content:
            continue
        # modify the thread by adding the files as either tool resources or file search files.
        await remote_thread.add_files_to_vector_store_async([file_content])
        # add external id to the data source

    logger.info(f"Added {len(files)} files to remote thread {remote_thread.id}")
