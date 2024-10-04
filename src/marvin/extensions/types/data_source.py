import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl

from marvin.extensions.utilities.unique_id import generate_id


class Glob(BaseModel):
    glob: str


class StartUrl(BaseModel):
    url: HttpUrl


class ProxyConfiguration(BaseModel):
    use_apify_proxy: bool


class WebSource(BaseModel):
    run_mode: Literal["DEVELOPMENT", "PRODUCTION"] = "DEVELOPMENT"
    start_urls: List[StartUrl]
    link_selector: str
    globs: List[Glob]
    pseudo_urls: List[str] = []
    excludes: List[Glob]
    page_function: str
    proxy_configuration: ProxyConfiguration
    initial_cookies: List[Any] = []
    wait_until: List[str] = ["networkidle2"]
    pre_navigation_hooks: Optional[str] = None
    post_navigation_hooks: Optional[str] = None
    breakpoint_location: Literal["NONE", "BEFORE_GOTO", "AFTER_GOTO"] = "NONE"
    custom_data: Dict[str, Any] = {}


class IndexData(BaseModel):
    mime_type: Optional[str] = None
    base64_string: Optional[str] = None
    prompt: Optional[str] = None


class ReferenceMetadata(BaseModel):
    file_id: str | None = None
    detail: str | None = None
    model_config = dict(extra="allow")


class DataSourceFileUpload(BaseModel):
    file: Any
    file_name: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    file_id: str | None = None
    file_upload_url: str | None = None
    file_upload_type: str | None = None
    reference_file_id: str | None = None
    file_path: str | None = None


class FileStoreMetadata(BaseModel):
    """
    Information about where the file is stored.
    """

    storage_type: Literal["local", "s3", "gcs", "memory"] = "local"
    bucket: str | None = None
    file_id: str | None = None
    file_name: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    file_path: str | None = None
    created: datetime | None = None
    modified: datetime | None = None
    presigned_url: str | None = None
    url: str | None = None


class VectorStoreMetadata(BaseModel):
    """
    Information about how the file is indexed.
    """

    vector_store_id: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    chunk_strategy: Literal["default", "high_density", "low_density"] = "default"


class ExternalFileReference(BaseModel):
    """
    Reference to a file in an external system.
    """

    file_id: str
    type: Literal["file_reference", "vector_store_reference"] = "file_reference"
    purpose: Literal["file_search", "code_interpreter", "image"] = "file_search"

    model_config = dict(extra="allow")


class DataSource(BaseModel):
    id: Optional[str | uuid.UUID] = Field(default_factory=lambda: generate_id("ds"))
    name: Optional[str] = None
    file_id: Optional[str] = Field(
        description="File ID from request. If not provided, a new UUID will be generated.",
        default_factory=lambda: str(uuid.uuid4()),
    )

    upload_url: Optional[HttpUrl] = None
    upload_type: Literal["file", "image", "url"] = Field(
        description="Source of the document: file upload, image upload, URL, or web scraping source.",
        default="file",
    )
    description: Optional[str] = None
    created: Optional[datetime] = Field(default_factory=datetime.now)
    modified: Optional[datetime] = Field(default_factory=datetime.now)
    index: Optional[IndexData] = None
    url: Optional[HttpUrl] = Field(
        description="URL of the data source if upload_type is 'url'",
        default=None,
    )
    source_type: Literal["file", "image", "url", "web_source", "video", "audio"] = (
        "file"
    )
    web_source: Optional[WebSource] = Field(
        description="Web scraping configuration if upload_type is 'web_source'",
        default=None,
    )
    status: Literal[
        "stored", "indexing", "indexed", "indexing_failed", "done", "uploaded"
    ] = "stored"

    # reference fields
    vector_store_metadata: Optional[VectorStoreMetadata] = None
    metadata: Optional[ReferenceMetadata] = None
    file_store_metadata: Optional[FileStoreMetadata] = None
    external_file_reference: Optional[ExternalFileReference] = None

    reference: Optional[dict] = Field(
        default=None, description="Reference to the file in the file store."
    )

    class Config:
        extra = "allow"

    def from_file_upload(cls, upload: DataSourceFileUpload):
        """
        Create a DataSource from a file upload.
        DataSource objects can store metadata about a file.
        """
        return cls(
            name=upload.file_name,
            description=upload.file_name,
            file_name=upload.file_name,
            file_type=upload.file_type,
            file_size=upload.file_size,
            file_id=upload.file_id,
            file_upload_url=upload.file_upload_url,
            file_upload_type=upload.file_upload_type,
        )

    def as_reference(self):
        return {
            "file_id": self.reference_file_id,
            "type": "file_reference",
        }

    @classmethod
    def test_data_source(cls):
        return cls(
            name="Test Data Source",
            description="This is a test data source",
            file_name="test.txt",
            file_type="text/plain",
            file_size=100,
            file_id="test_file_id",
        )


class VectorStore(BaseModel):
    id: Optional[str | uuid.UUID] = Field(default_factory=lambda: generate_id("vs"))
    name: str
    data_source_ids: List[str]
