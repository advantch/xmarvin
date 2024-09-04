from pydantic import BaseModel, Field, HttpUrl
from typing import BinaryIO, List, Optional, Literal, Dict, Any
import uuid
from datetime import datetime

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

class DataSourceFileUpload(BaseModel):
    file: Any
    file_name: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    file_id: str | None = None
    file_upload_url: str | None = None
    file_upload_type: str | None = None
    reference_file_id: str | None = None

class DataSource(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    file_name: Optional[str] = None
    file_id: Optional[str] = Field(
        description="File ID from request. If not provided, a new UUID will be generated.",
        default_factory=lambda: str(uuid.uuid4()),
    )
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    upload_url: Optional[HttpUrl] = None
    upload_type: Literal["file", "image", "url", "web_source"] = Field(
        description="Source of the document: file upload, image upload, URL, or web scraping source.",
        default="file",
    )
    description: Optional[str] = None
    chunks_length: Optional[int] = None
    chunks_strategy: Optional[Literal["default", "high_density", "low_density"]] = Field(
        description="Strategy for chunking the document",
        default="default",
    )
    temporary: Optional[bool] = None
    created: Optional[datetime] = Field(default_factory=datetime.now)
    modified: Optional[datetime] = Field(default_factory=datetime.now)
    index: Optional[IndexData] = None
    url: Optional[HttpUrl] = Field(
        description="URL of the data source if upload_type is 'url'",
        default=None,
    )
    web_source: Optional[WebSource] = Field(
        description="Web scraping configuration if upload_type is 'web_source'",
        default=None,
    )
    status: Literal["loaded", "indexing", "indexed", "failed", ""] = "loaded"
    reference_file_id: Optional[str] = Field(
        description="Reference file ID. Use this to generate presigned upload URLs.",
        default=None,
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


    
