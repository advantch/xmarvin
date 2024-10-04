import os

import pytest

from marvin.beta.assistants import Thread
from marvin.beta.local.thread import LocalThread
from marvin.extensions.storage.data_source_store import InMemoryDataSourceStore
from marvin.extensions.types.data_source import DataSource
from marvin.extensions.utilities.setup_storage import setup_memory_stores
from marvin.extensions.utilities.unique_id import generate_id
from marvin.utilities.openai import get_openai_client

data_source_storage = InMemoryDataSourceStore()


@pytest.fixture
def test_file():
    with open("test_file.txt", "wb") as file:
        file.write(b"Test file content")
    yield file
    os.remove("test_file.txt")


@pytest.mark.asyncio
async def test_thread_synchronizer(test_file):
    # Setup

    tenant_id = generate_id("tenant")
    openai_client = get_openai_client()

    local_thread: LocalThread = await LocalThread.create_async(
        id=generate_id("thread"),
        tenant_id=tenant_id,
    )

    setup_memory_stores()

    remote_thread: Thread = Thread()
    remote_thread = await remote_thread.create_async()
    assert remote_thread.id is not None

    assert local_thread.thread_storage is not None

    file_path = os.path.join(os.path.dirname(__file__), "f.txt")
    # write some content to the file
    with open(file_path, "wb") as file:
        file.write(b"Test file content")
    # upload the file to openai
    with open(file_path, "rb") as file:
        file = await openai_client.files.create(file=file, purpose="assistants")
        file_search_attachments = [
            dict(file_id=file.id, tools=[dict(type="file_search")])
        ]
    await remote_thread.add_async(
        "search", file_search_attachments=file_search_attachments
    )
    # check file available

    remote_files = await remote_thread.get_vector_store_files_async()
    assert len(remote_files) == 1, remote_files
    assert remote_files[0].id == file.id, remote_files[0].id

    # add a file to local thread
    DataSource.test_data_source()
    # with open(file_path, "rb") as file:
    #     file_metadata = await stores.file_storage.save_file_async(file, file_name="test_file.txt")
    #     data_source.file_store_metadata = file_metadata
    # data_source = await data_source_storage.save_async(
    #     data_source
    # )
    # await local_thread.add_data_source_async(data_source)

    # # check file available
    # local_files = await local_thread.get_files_async()

    # _, file = local_files[0]
    # assert file.size > 0, file.sizee
    # assert len(local_files) == 1, local_files
    # assert isinstance(local_files[0][1], ContentFile)

    # # add files to remote thread.
    # await sync_files_to_remote_thread(local_thread, remote_thread)

    # # Cleanup
    # remote_files = await remote_thread.get_vector_store_files_async()
    # await remote_thread.delete_async()
    # for file in remote_files:
    #     await openai_client.files.delete(file.id)
