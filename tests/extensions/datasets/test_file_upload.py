import pytest
import uuid
import httpx
import magic
from io import BytesIO
from unittest.mock import AsyncMock, patch
from marvin.extensions.storage.file_storage import LocalFileStorage
from marvin.extensions.types.data_source import DataSource

pytestmark = pytest.mark.asyncio

@pytest.fixture
def file_storage():
    return LocalFileStorage()

async def test_presigned_url(file_storage):
    file_id = str(uuid.uuid4())
    
    # Mock the request_presigned_url method
    with patch.object(file_storage, 'request_presigned_url', new_callable=AsyncMock) as mock_request_url:
        mock_request_url.return_value = {
            "id": file_id,
            "upload_url": f"https://example.com/upload/{file_id}",
        }
        
        response = await file_storage.request_presigned_url_async(file_id, private=False)

        assert response is not None
        assert "upload_url" in response
        upload_url = response["upload_url"]

        # Simulate file upload
        file_content = b"test"
        mime = magic.Magic(mime=True)
        content_type = mime.from_buffer(file_content)
        
        with patch('httpx.put') as mock_put:
            mock_put.return_value.status_code = 200
            mock_put.return_value.text = ""
            
            res = await file_storage.save_file_async(BytesIO(file_content), file_id, {"size": len(file_content), "content_type": content_type})
            assert res["file_id"] == file_id
            assert res["size"] == 4
            assert res["content_type"] == content_type

        # Verify file content
        file = await file_storage.get_file_async(file_id)
        assert file.read() == file_content

        # Simulate public access
        with patch('httpx.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.text = "test"
            mock_get.return_value.headers = {"Content-Type": content_type}
            
            file_metadata = await file_storage.get_file_metadata_async(file_id)
            res = httpx.get(file_metadata.get("url", ""))
            assert res.status_code == 200
            assert res.text == "test"
            assert res.headers["Content-Type"] == content_type

    # Test public file
    file_id2 = str(uuid.uuid4())
    with patch.object(file_storage, 'request_presigned_url', new_callable=AsyncMock) as mock_request_url:
        mock_request_url.return_value = {
            "id": file_id2,
            "upload_url": f"https://example.com/upload/{file_id2}",
        }
        
        response = await file_storage.request_presigned_url_async(file_id2, private=False)
        assert response is not None
        assert "upload_url" in response


        # Simulate file upload
        file_content = b"test-public"
        content_type = mime.from_buffer(file_content)
        
        with patch('httpx.put') as mock_put:
            mock_put.return_value.status_code = 200
            mock_put.return_value.text = ""
            
            res = await file_storage.save_file_async(BytesIO(file_content), file_id2, {"size": len(file_content), "content_type": content_type})
            assert res["file_id"] == file_id2
            assert res["size"] == 11
            assert res["content_type"] == content_type

        # Verify file content
        file = await file_storage.get_file_async(file_id2)
        assert file.read() == file_content

        # Simulate public access
        with patch('httpx.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.text = "test-public"
            mock_get.return_value.headers = {"Content-Type": content_type}
            
            file_metadata = await file_storage.get_file_metadata_async(file_id2)
            res = httpx.get(file_metadata.get("url", ""))
            assert res.status_code == 200
            assert res.text == "test-public"
            assert res.headers["Content-Type"] == content_type