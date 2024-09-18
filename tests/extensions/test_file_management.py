import pytest
import uuid
from marvin.beta.assistants import Thread, Assistant
from marvin.utilities.openai import get_openai_client
from marvin.beta.local.thread import LocalThread
from marvin.extensions.storage.base import BaseThreadStore
from marvin.extensions.utilities.sync_threads import ThreadSynchronizer, sync_thread

@pytest.mark.asyncio
async def test_thread_synchronizer():
    # Setup
    openai_client = get_openai_client()
    local_thread = LocalThread(tenant_id=uuid.uuid4())
    remote_thread = await Thread().create_async()
    thread_store = local_thread.thread_storage
    
    synchronizer = ThreadSynchronizer(local_thread, remote_thread)
    assert local_thread.thread_storage is not None

    # Test sync_files
    await synchronizer.sync_files()

    # Add a file to the remote thread
    file_content = b"Test file content"
    file = await openai_client.files.create(file=file_content, purpose="assistants")
    await remote_thread.add_async(file_ids=[file.id])

    # Sync again
    await synchronizer.sync_files()

    # Verify that the file was synced to the local thread
    local_files = await local_thread.list_files_async()
    assert len(local_files) == 1
    assert local_files[0].id == file.id

    # Test sync_vector_store
    await synchronizer.sync_vector_store()

    # Create a vector store for the remote thread
    vector_store_id = await remote_thread.create_vector_store_async("Thread Vector Store")
    
    # Sync again
    await synchronizer.sync_vector_store()

    # Verify that the vector store was synced to the local thread
    assert await local_thread.has_vector_store_async()
    assert local_thread.vector_store_id == vector_store_id

    # Test full sync_thread function
    await sync_thread(local_thread, remote_thread)

    # Assert that local thread's external_id is updated
    assert local_thread.external_id == remote_thread.id

    # Cleanup
    await remote_thread.delete_async()
    await openai_client.files.delete(file.id)