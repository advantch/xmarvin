import uuid

import pytest

from marvin.extensions.file_storage.local_file_storage import (
    LocalFileStorage,
)
from marvin.extensions.types import ChatMessage, Metadata
from marvin.extensions.types.data_source import DataSource, WebSource
from marvin.extensions.types.message import FileMessageContent, ImageMessageContent
from marvin.extensions.utilities.file_utilities import ContentFile

pytestmark = pytest.mark.asyncio


@pytest.fixture
def file_storage():
    return LocalFileStorage()


@pytest.mark.asyncio
@pytest.mark.no_llm
async def test_parse_file_attachments(file_storage):
    # Create an image file uploa
    # real image content example in binary

    # Create a simple 1x1 pixel PNG image in binary format
    image_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    im = await file_storage.save_file_async(
        ContentFile(image_content, name="image.png"),
        file_id=str(uuid.uuid4()),
    )

    # Create a document file upload
    # real document content example in binary
    doc_content = b"%PDF-1.7\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<<>>/Contents 4 0 R>>\nendobj\n4 0 obj\n<</Length 21>>stream\nBT\n/F1 12 Tf\n100 700 Td\n(Hello, World!) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000102 00000 n\n0000000192 00000 n\ntrailer\n<</Size 5/Root 1 0 R>>\nstartxref\n264\n%%EOF"
    doc = await file_storage.save_file_async(
        ContentFile(doc_content, name="document.pdf"),
        file_id=str(uuid.uuid4()),
    )

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
                ImageMessageContent(file_id=im.file_id, type="image"),
                FileMessageContent(file_id=doc.file_id, type="file"),
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


@pytest.mark.no_llm
def test_valid_web_source_data_source(valid_web_source_config):
    data_source = DataSource(
        name="Web Scraper Test",
        upload_type="url",
        web_source=WebSource(**valid_web_source_config),
    )
    assert data_source.upload_type == "url"
    assert isinstance(data_source.web_source, WebSource)
    assert data_source.web_source.run_mode == "DEVELOPMENT"
    assert len(data_source.web_source.start_urls) == 1
    assert (
        str(data_source.web_source.start_urls[0].url).rstrip("/")
        == "https://crawlee.dev"
    )


@pytest.mark.no_llm
def test_url_data_source():
    data_source = DataSource(
        name="URL Test", upload_type="url", url="https://example.com/data.json"
    )
    assert data_source.upload_type == "url"
    assert str(data_source.url) == "https://example.com/data.json"
