from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union

from marvin.extensions.storage.base import BaseStorage
from marvin.extensions.types import ChatMessage
from marvin.utilities.asyncio import ExposeSyncMethodsMixin


class BaseMemory(ABC, ExposeSyncMethodsMixin):
    @abstractmethod
    def __init__(
        self, storage: Optional[BaseStorage] = None, context: Optional[Dict] = None
    ):
        pass

    @abstractmethod
    async def load_async(self) -> Dict[str, List[ChatMessage]]:
        pass

    @abstractmethod
    async def put_async(
        self, message: ChatMessage, index: Optional[str] = None, persist: bool = True
    ) -> Dict[str, List[ChatMessage]]:
        pass

    @abstractmethod
    async def get_async(self, index: str) -> List[ChatMessage]:
        pass

    @abstractmethod
    async def get_all_async(self) -> Dict[str, List[ChatMessage]]:
        pass

    @abstractmethod
    async def get_messages_async(
        self, index: Optional[str] = None, as_dicts: bool = True
    ) -> Union[List[Dict], List[ChatMessage]]:
        pass

    @abstractmethod
    async def get_last_message_async(
        self, index: Optional[str] = None, as_dicts: bool = False
    ) -> Optional[Union[Dict, ChatMessage]]:
        pass
