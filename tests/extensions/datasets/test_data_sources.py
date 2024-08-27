import uuid
import pytest
import respx
import httpx
from io import BytesIO
from unittest.mock import AsyncMock, patch
from marvin.extensions.storage.file_storage import SimpleFileStorage
from marvin.extensions.types import ChatMessage, Metadata
from marvin.extensions.types.message import FileMessageContent, ImageMessageContent
from marvin.extensions.types.data_source import DataSource, WebSource
from openai.types.file_object import FileObject
from openai.types.beta.thread import Thread
from openai.types.beta.threads.message import Message
from openai.types.beta.threads.message_content import MessageContent, TextContentBlock
from openai.types.beta.threads.text import Text

pytestmark = pytest.mark.asyncio

@pytest.fixture
def file_storage():
    return SimpleFileStorage()

async def test_parse_file_attachments(file_storage):
    # Create an image file upload
    image_content = b"fake image content"
    image_file = BytesIO(image_content)
    im = await file_storage.save_file(image_file, "image.png", metadata={"content_type": "image/png"})

    # Create a document file upload
    doc_content = b"fake document content"
    doc_file = BytesIO(doc_content)
    doc = await file_storage.save_file(doc_file, "document.pdf", metadata={"content_type": "application/pdf"})

    # Check if the files are saved to the storage
    im_obj = await file_storage.get_file_metadata(im["file_id"])
    assert im_obj["content_type"] == "image/png"

    doc_obj = await file_storage.get_file_metadata(doc["file_id"])
    assert doc_obj["content_type"] == "application/pdf"

    # Create a message and try parse it
    message = ChatMessage(
        id=str(uuid.uuid4()),
        role="user",
        run_id=None,
        content=[
            {
                "text": {"value": "describe the image", "annotations": []},
                "type": "text",
            },
        ],
        metadata=Metadata(
            id="",
            name=None,
            type="message",
            run_id="",
            streaming=False,
            raw_output=None,
            tool_calls=None,
            attachments=[
                ImageMessageContent(file_id=im["file_id"], type="image"),
                FileMessageContent(file_id=doc["file_id"], type="file"),
            ],
        ),
        thread_id=str(uuid.uuid4()),
    )

    attachment_types = [a.type for a in message.metadata.attachments]
    assert "image" in attachment_types
    assert "file" in attachment_types

    # Check attachments parsing
    for attachment in message.metadata.attachments:
        if attachment.type == "image":
            assert isinstance(attachment, ImageMessageContent)
        elif attachment.type == "file":
            assert isinstance(attachment, FileMessageContent)

@pytest.fixture
def valid_web_source_config():
    return {
        "run_mode": "DEVELOPMENT",
        "start_urls": [{"url": "https://crawlee.dev"}],
        "link_selector": "a[href]",
        "globs": [{"glob": "https://crawlee.dev/*/*"}],
        "excludes": [{"glob": "/**/*.{png,jpg,jpeg,pdf}"}],
        "page_function": "async function pageFunction(context) { /* ... */ }",
        "proxy_configuration": {"use_apify_proxy": True},
    }

def test_valid_web_source_data_source(valid_web_source_config):
    data_source = DataSource(
        name="Web Scraper Test",
        upload_type="web_source",
        web_source=WebSource(**valid_web_source_config)
    )
    assert data_source.upload_type == "web_source"
    assert isinstance(data_source.web_source, WebSource)
    assert data_source.web_source.run_mode == "DEVELOPMENT"
    assert len(data_source.web_source.start_urls) == 1
    assert str(data_source.web_source.start_urls[0].url).rstrip('/') == "https://crawlee.dev"

def test_invalid_web_source_data_source():
    with pytest.raises(ValueError, match="web_source must be provided when upload_type is 'web_source'"):
        DataSource(name="Invalid Web Source", upload_type="web_source")

def test_web_source_with_invalid_upload_type(valid_web_source_config):
    with pytest.raises(ValueError, match="web_source should only be provided when upload_type is 'web_source'"):
        DataSource(
            name="Invalid Upload Type",
            upload_type="file",
            web_source=WebSource(**valid_web_source_config)
        )

def test_url_data_source():
    data_source = DataSource(
        name="URL Test",
        upload_type="url",
        url="https://example.com/data.json"
    )
    assert data_source.upload_type == "url"
    assert str(data_source.url) == "https://example.com/data.json"

def test_invalid_url_data_source():
    with pytest.raises(ValueError, match="URL must be provided when upload_type is 'url'"):
        DataSource(name="Invalid URL", upload_type="url")

def test_url_with_invalid_upload_type():
    with pytest.raises(ValueError, match="URL should only be provided when upload_type is 'url'"):
        DataSource(
            name="Invalid Upload Type",
            upload_type="file",
            url="https://example.com/data.json"
        )

async def test_upload_from_url(file_storage):
    url = "https://example.com/test_file.txt"
    file_id = str(uuid.uuid4())

    with patch.object(file_storage, 'download_file', new_callable=AsyncMock) as mock_download:
        mock_download.return_value = {"file_id": file_id, "url": url}

        data_source = DataSource(
            name="test_file",
            upload_type="url",
            url=url,
        )

        doc_json = await file_storage.download_file(url, file_id)

        assert str(data_source.url) == url

@respx.mock
async def test_sync_with_openai_thread(file_storage):
    thread_id = str(uuid.uuid4())
    
    # Prepare mock responses
    thread_response = {
        "id": thread_id,
        "created_at": 1699012949,
        "metadata": {},
        "object": "thread",
        "tool_resources": None
    }
    message_response = {
        "id": "msg_1",
        "object": "thread.message",
        "created_at": 1699012950,
        "thread_id": thread_id,
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": {
                    "value": "Hello",
                    "annotations": []
                }
            }
        ],
        "file_ids": ["file1", "file2"],
        "assistant_id": None,
        "run_id": None,
        "metadata": {},
        "status": "completed"
    }
    
    messages_response = {
        "object": "list",
        "data": [message_response],
        "first_id": "msg_1",
        "last_id": "msg_1",
        "has_more": False
    }
    file1_response = {
        "id": "file1",
        "bytes": 120000,
        "created_at": 1699012949,
        "filename": "file1.txt",
        "object": "file",
        "purpose": "assistants",
        "status": "processed",
        "status_details": None
    }
    
    file2_response = {
        "id": "file2",
        "bytes": 140000,
        "created_at": 1699012950,
        "filename": "file2.txt",
        "object": "file",
        "purpose": "assistants",
        "status": "processed",
        "status_details": None
    }

    # Mock the OpenAI API calls
    respx.get(f"https://api.openai.com/v1/threads/{thread_id}").mock(
        return_value=httpx.Response(200, json=thread_response)
    )
    respx.get(f"https://api.openai.com/v1/threads/{thread_id}/messages").mock(
        return_value=httpx.Response(200, json=messages_response)
    )
    respx.get("https://api.openai.com/v1/files/file1").mock(
        return_value=httpx.Response(200, json=file1_response)
    )
    respx.get("https://api.openai.com/v1/files/file2").mock(
        return_value=httpx.Response(200, json=file2_response)
    )
    respx.get("https://api.openai.com/v1/files/file1/content").mock(
        return_value=httpx.Response(200, content=b"file content 1")
    )
    respx.get("https://api.openai.com/v1/files/file2/content").mock(
        return_value=httpx.Response(200, content=b"file content 2")
    )

    with patch('marvin.utilities.openai.get_openai_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.beta.threads.retrieve.return_value = Thread(**thread_response)
        mock_client.beta.threads.messages.list.return_value = AsyncMock(
            data=[Message(**messages_response["data"][0])]
        )
        mock_client.files.retrieve.side_effect = [
            FileObject(**file1_response),
            FileObject(**file2_response)
        ]
        mock_client.files.content.side_effect = [
            AsyncMock(aread=AsyncMock(return_value=b"file content 1")),
            AsyncMock(aread=AsyncMock(return_value=b"file content 2"))
        ]

        synced_files = await file_storage.sync_with_openai_thread(thread_id)

    assert len(synced_files) == 2
    for file in synced_files:
        assert "file_id" in file
        assert "purpose" in file
        assert file["purpose"] == "assistants"

@respx.mock
async def test_sync_with_openai_assistant(file_storage):
    assistant_id = str(uuid.uuid4())

    # Mock the OpenAI API calls
    respx.get(f"https://api.openai.com/v1/assistants/{assistant_id}").mock(
        return_value=httpx.Response(200, json={
            "id": assistant_id,
            "file_ids": ["file1", "file2"]
        })
    )
    respx.get("https://api.openai.com/v1/files/file1").mock(
        return_value=httpx.Response(200, json={"purpose": "assistants"})
    )
    respx.get("https://api.openai.com/v1/files/file2").mock(
        return_value=httpx.Response(200, json={"purpose": "assistants"})
    )
    respx.get("https://api.openai.com/v1/files/file1/content").mock(
        return_value=httpx.Response(200, content=b"file content")
    )
    respx.get("https://api.openai.com/v1/files/file2/content").mock(
        return_value=httpx.Response(200, content=b"file content")
    )

    synced_files = await file_storage.sync_with_openai_assistant(assistant_id)

    assert len(synced_files) == 2
    for file in synced_files:
        assert "file_id" in file
        assert "purpose" in file
        assert file["purpose"] == "assistants"

@respx.mock
async def test_upload_to_openai(file_storage):
    file_id = str(uuid.uuid4())
    purpose = "assistants"

    # Prepare a file in the storage
    file_content = b"test file content"
    await file_storage.save_file(BytesIO(file_content), file_id, {"filename": "test.txt"})

    # Mock the OpenAI API call
    respx.post("https://api.openai.com/v1/files").mock(
        return_value=httpx.Response(200, json={
            "id": "openai_file_id",
            "purpose": purpose
        })
    )

    result = await file_storage.upload_to_openai(file_id, purpose)

    assert result["id"] == "openai_file_id"
    assert result["purpose"] == purpose

    # Check if local metadata was updated
    metadata = await file_storage.get_file_metadata(file_id)
    assert metadata["openai_file_id"] == "openai_file_id"

async def test_presigned_url(file_storage):
    file_id = str(uuid.uuid4())

    response = await file_storage.request_presigned_url(file_id, private=False)

    assert response is not None
    assert "upload_url" in response
    upload_url = response["upload_url"]

    # Simulate file upload
    file_content = b"test"
    with patch('httpx.put') as mock_put:
        mock_put.return_value.status_code = 200
        mock_put.return_value.text = ""

        await file_storage.save_file(BytesIO(file_content), file_id, {"size": len(file_content)})

    # Verify file content
    file = await file_storage.get_file(file_id)
    assert file.read() == file_content

    # Simulate public access
    with patch('httpx.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "test"

        file_metadata = await file_storage.get_file_metadata(file_id)
        res = httpx.get(file_metadata.get("url", ""))
        assert res.status_code == 200
        assert res.text == "test"