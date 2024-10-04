import os
import uuid

import pytest

from marvin.extensions.file_storage.local_file_storage import LocalFileStorage
from marvin.extensions.types.data_source import FileStoreMetadata
from marvin.extensions.utilities.file_utilities import ContentFile, SimpleUploadedFile


@pytest.fixture
def file_storage(tmp_path=""):
    # Instantiate the LocalFileStorage with a temporary directory
    storage = LocalFileStorage()
    return storage


@pytest.fixture
def test_file():
    file_content = b"Test file content"
    file = ContentFile(name="test_file.txt", content=file_content)
    return file, file_content


@pytest.mark.asyncio
async def test_save_and_get_file(file_storage, test_file):
    file, file_content = test_file
    file_id = str(uuid.uuid4())
    file_name = file.name

    # Test saving a file
    file_metadata = await file_storage.save_file_async(
        file, file_id=file_id, file_name=file_name
    )

    assert file_metadata.file_id == file_id
    assert file_metadata.file_size == len(file_content)
    assert file_metadata.file_name == file_name
    assert os.path.exists(file_metadata.file_path)

    # Test getting the file
    retrieved_file = await file_storage.get_file_async(file_metadata)
    assert retrieved_file is not None


@pytest.mark.asyncio
async def test_delete_file(file_storage, test_file):
    file, _ = test_file
    file_id = str(uuid.uuid4())

    # Save the file
    file_metadata = await file_storage.save_file_async(file, file_id=file_id)

    # Delete the file
    await file_storage.delete_file_async(file_metadata)
    assert not os.path.exists(file_metadata.file_path)

    # Try to get the file (should raise an error)
    with pytest.raises(FileNotFoundError):
        await file_storage.get_file_async(file_metadata)


@pytest.mark.asyncio
async def test_download_file(file_storage):
    url = "https://example-files.online-convert.com/document/txt/example.txt"
    file_id = str(uuid.uuid4())
    content = b"Downloaded file content"

    # Mock the download_file_async method
    async def mock_download_file_async(url, file_id):
        await file_storage.save_file_async(
            SimpleUploadedFile(name="test_file.txt", content=content), file_id
        )
        return FileStoreMetadata(
            file_id=file_id,
            file_size=len(content),
            file_name=f"{file_id}.txt",
            file_type="file",
            file_path=os.path.join(file_storage.base_path, file_id),
        )

    file_storage.download_file_async = mock_download_file_async

    file_metadata = await file_storage.download_file_async(url, file_id)
    assert file_metadata.file_id == file_id

    # Verify the file was saved
    retrieved_file = await file_storage.get_file_async(file_metadata)
    assert retrieved_file is not None


@pytest.mark.asyncio
async def test_request_presigned_url(file_storage):
    file_id = str(uuid.uuid4())

    response = await file_storage.request_presigned_url_async(file_id, private=False)

    assert response is not None
    assert response["id"] == file_id
    assert "upload_url" in response


@pytest.mark.asyncio
async def test_save_content_file(file_storage):
    file_content = b"Sample text content"
    file = ContentFile(file_content, name="sample.txt")
    file_id = str(uuid.uuid4())

    # Save the content file
    file_metadata = await file_storage.save_file_async(
        file, file_id=file_id, file_name=file.name
    )

    assert file_metadata.file_name == "sample.txt"
    assert file_metadata.file_size == len(file_content)

    # Retrieve and verify the content
    retrieved_file = await file_storage.get_file_async(file_metadata)

    assert retrieved_file is not None


@pytest.mark.asyncio
async def test_save_binary_file(file_storage):
    file_content = b"\x00\x01\x02\x03"
    file = SimpleUploadedFile(name="image.png", content=file_content)
    file_id = str(uuid.uuid4())

    # Save the binary file
    file_metadata = await file_storage.save_file_async(
        file, file_id=file_id, file_name=file.name
    )

    assert file_metadata.file_name == "image.png"
    assert file_metadata.file_size == len(file_content)

    # Retrieve and verify the content
    retrieved_file = await file_storage.get_file_async(file_metadata)
    assert retrieved_file is not None
