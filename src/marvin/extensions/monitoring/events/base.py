from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(), alias="timestamp"
    )
    id_: str = Field(default_factory=lambda: str(uuid4()), description="Event ID")
    span_id: str = Field(default_factory=str, description="Span ID")
    merge_id: str = Field(default_factory=lambda: str(uuid4()), description="Merge ID")
    parent_id: str | None = Field(None, description="Parent Event ID")

    class Config:
        arbitrary_types_allowed = True
        defer_build = False

    @classmethod
    def class_name(cls):
        """Return class name."""
        return "BaseEvent"

    def dict(self, **kwargs: Any) -> Dict[str, Any]:
        data = super().dict(**kwargs)
        data["class_name"] = self.class_name()
        return data


def build_event_tree(events: list[BaseEvent]) -> dict:
    # loop through all events
    pass
