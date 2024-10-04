"""Base interface classes for interacting with local storage objects."""

from abc import ABC
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

from marvin.utilities.asyncio import ExposeSyncMethodsMixin

T = TypeVar("T")


class BaseStorage(ABC, Generic[T], ExposeSyncMethodsMixin):
    """
    Interface for storage classes.
    API between RuntimeMemory and storage layers.
    """

    model: BaseModel = Field(
        ..., description="The model type for the storage. Required."
    )

    model_config = dict(arbitrary_types_allowed=True)

    async def save_async(self, item: T) -> None:
        raise NotImplementedError("save not implemented")

    async def get_async(
        self, id: str, extra_params: Optional[dict] = None
    ) -> Optional[T]:
        raise NotImplementedError("get_async not implemented")

    async def list_async(self, filter_params: Optional[dict] = None) -> List[T]:
        raise NotImplementedError("list_async not implemented")
