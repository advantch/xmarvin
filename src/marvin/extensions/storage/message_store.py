from typing import List, Optional

from marvin.extensions.storage.base import BaseStorage
from marvin.extensions.storage.redis_base import RedisBase
from marvin.extensions.types import ChatMessage
from marvin.extensions.types.tools import (
    AppCodeInterpreterTool,
    AppFileSearchTool,
    AppToolCall,
)
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method


class BaseMessageStore(BaseStorage[ChatMessage], ExposeSyncMethodsMixin):
    @expose_sync_method("update_message_tool_calls")
    async def update_message_tool_calls_async(
        self, thread_id: str, file_id: str, data_source
    ) -> None:
        """
        Update the tool calls for a message.
        """
        raise NotImplementedError("update_message_tool_calls_async not implemented")

    @expose_sync_method("save")
    async def save_async(self, message: ChatMessage) -> None:
        raise NotImplementedError("save_async not implemented")

    @expose_sync_method("get")
    async def get_async(self, message_id: str) -> Optional[ChatMessage]:
        raise NotImplementedError("get_async not implemented")

    @expose_sync_method("list")
    async def list_async(self, thread_id: str) -> List[ChatMessage]:
        raise NotImplementedError("list_async not implemented")

    @expose_sync_method("get_thread_messages")
    async def get_thread_messages_async(self, thread_id: str) -> List[ChatMessage]:
        raise NotImplementedError("get_thread_messages_async not implemented")


class InMemoryMessageStore(BaseMessageStore):
    def __init__(self):
        self.messages = {}

    @expose_sync_method("save")
    async def save_async(self, message: ChatMessage, thread_id: str = None) -> None:
        self.messages[message.id] = message

    @expose_sync_method("get")
    async def get_async(self, message_id: str) -> Optional[ChatMessage]:
        return self.messages.get(message_id)

    @expose_sync_method("list")
    async def list_async(
        self, thread_id: str, filter_params: Optional[dict] = None
    ) -> List[ChatMessage]:
        if not filter_params:
            return list(self.messages.values())
        return [
            msg
            for msg in self.messages.values()
            if all(getattr(msg, k, None) == v for k, v in filter_params.items())
        ]

    @expose_sync_method("get_thread_messages")
    async def get_thread_messages_async(self, thread_id: str) -> List[ChatMessage]:
        return [msg for msg in self.messages.values() if msg.thread_id == thread_id]


class DjangoMessageStore(BaseMessageStore):
    def __init__(self, model):
        self.model = model

    @expose_sync_method("save")
    async def save_async(self, message: ChatMessage, thread_id: str = None) -> None:
        await self.model.objects.update_or_create(
            id=message.id, defaults=message.model_dump()
        )

    @expose_sync_method("get")
    async def get_async(self, message_id: str) -> Optional[ChatMessage]:
        message = await self.model.objects.filter(id=message_id).first()
        return ChatMessage.model_validate(message) if message else None

    @expose_sync_method("list")
    async def list_async(
        self, thread_id: str, filter_params: Optional[dict] = None
    ) -> List[ChatMessage]:
        queryset = self.model.objects.filter(thread_id=thread_id)
        if filter_params:
            queryset = queryset.filter(**filter_params)
        messages = await queryset
        return [ChatMessage.model_validate(message) for message in messages]

    @expose_sync_method("get_thread_messages")
    async def get_thread_messages_async(self, thread_id: str) -> List[ChatMessage]:
        queryset = self.model.objects.filter(thread_id=thread_id)
        messages = await queryset
        return [ChatMessage.model_validate(message) for message in messages]

    @expose_sync_method("update_message_tool_calls")
    async def update_message_tool_calls_async(
        self, thread_id: str, file_id: str, data_source
    ) -> None:
        """
        Update the tool calls for a message.
        """
        messages = self.model.objects.filter(
            thread_id=thread_id, metadata__tool_calls__code_interpreter__isnull=False
        )
        for message in messages:
            chat_message = ChatMessage.model_validate(message.model_data)
            if chat_message.metadata.tool_calls:
                tc = []
                for tool_call in chat_message.metadata.tool_calls:
                    if getattr(tool_call, "code_interpreter", None):
                        for output in tool_call.code_interpreter.outputs:
                            if getattr(output, "image", None):
                                if output.image.file_id == file_id:
                                    tool_call.structured_output = {
                                        "type": "image_url",
                                        "image_url": {"url": data_source.url},
                                    }

                    if tool_call.type == "code_interpreter":
                        tool_call = AppCodeInterpreterTool.model_validate(
                            tool_call.model_dump()
                        )
                    if tool_call.type == "file_search":
                        tool_call = AppFileSearchTool.model_validate(
                            tool_call.model_dump()
                        )
                    if tool_call.type == "function":
                        tool_call = AppToolCall.model_validate(tool_call.model_dump())
                    tc.append(tool_call)
                chat_message.metadata.tool_calls = tc
                ChatMessage.model_rebuild()
                message.model_data = chat_message.model_dump()
                message.save()


class RedisMessageStore(BaseMessageStore, RedisBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect()

    @expose_sync_method("save")
    async def save_async(self, message: ChatMessage) -> None:
        self.redis_client.set(f"message:{message.id}", message.model_dump_json())
        self.redis_client.sadd(f"thread:{message.thread_id}:messages", message.id)

    @expose_sync_method("get")
    async def get_async(self, message_id: str) -> Optional[ChatMessage]:
        message_data = self.redis_client.get(f"message:{message_id}")
        return ChatMessage.model_validate_json(message_data) if message_data else None

    @expose_sync_method("list")
    async def list_async(
        self, filter_params: Optional[dict] = None
    ) -> List[ChatMessage]:
        if filter_params and "thread_id" in filter_params:
            message_ids = self.redis_client.smembers(
                f"thread:{filter_params['thread_id']}:messages"
            )
            messages = [
                ChatMessage.model_validate_json(
                    self.redis_client.get(f"message:{msg_id}")
                )
                for msg_id in message_ids
            ]
        else:
            messages = [
                ChatMessage.model_validate_json(msg_data)
                for msg_data in self.redis_client.mget(
                    self.redis_client.keys("message:*")
                )
            ]

        if filter_params:
            return [
                msg
                for msg in messages
                if all(getattr(msg, k, None) == v for k, v in filter_params.items())
            ]
        return messages

    @expose_sync_method("get_thread_messages")
    async def get_thread_messages_async(self, thread_id: str) -> List[ChatMessage]:
        return await self.list_async(filter_params={"thread_id": thread_id})
