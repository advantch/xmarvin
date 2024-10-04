import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dotenv import load_dotenv

from marvin.extensions.file_storage.s3_storage import BucketConfig, S3Storage
from marvin.extensions.utilities.file_utilities import ContentFile

path = Path(__file__).parent.parent.parent.parent
load_dotenv(path / ".env")


@pytest.mark.asyncio
async def test_s3_file_storage():
    # Mock S3 client
    MagicMock()

    s3_storage = S3Storage(config=BucketConfig.from_env())

    # Test file content
    file_content = b"Test S3 file content"
    file = ContentFile(name="test_s3_file.txt", content=file_content)
    file_id = str(uuid.uuid4())

    # Test saving a file
    file_metadata = await s3_storage.save_file_async(
        file, file_id=file_id, file_name=file.name
    )

    assert file_metadata.file_id == file_id
    assert file_metadata.file_size == len(file_content)
    assert file_metadata.file_name == file.name

    # Test getting the file
    retrieved_file = await s3_storage.get_file_async(file_metadata)
    assert retrieved_file.read() == file_content

    # Test deleting the file
    await s3_storage.delete_file_async(file_metadata)
    # mock_s3_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key=file_id)

    # Test generating a presigned URL
    presigned_url = s3_storage.generate_presigned_url(file_metadata)
    assert presigned_url is not None

    file_id = str(uuid.uuid4())
    response = await s3_storage.request_presigned_url_async(file_id, private=False)

    assert response is not None
    assert response["id"] == file_id
    assert "upload_url" in response
