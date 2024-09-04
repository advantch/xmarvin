import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ChatThread(BaseModel):
    id: str | uuid.UUID | None = Field(default_factory=uuid.uuid4)
    name: Optional[str] = None
    tenant_id: Optional[str | uuid.UUID | int] = None
    created: datetime = Field(default_factory=datetime.utcnow)
    modified: datetime = Field(default_factory=datetime.utcnow)
    external_id: Optional[str] = None
    user_id: Optional[str | uuid.UUID | int] = None
    tags: List[str] | None = Field(default_factory=list)
    data: Optional[dict] = Field(default_factory=dict)
