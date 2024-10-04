from typing import List, Optional

from marvin.extensions.storage.base import BaseStorage
from marvin.extensions.storage.redis_base import RedisBase
from marvin.extensions.tools.tool import Tool
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method


class BaseToolStore(BaseStorage[Tool], ExposeSyncMethodsMixin):
    @expose_sync_method("save_tool")
    async def save_tool_async(self, tool: Tool) -> None:
        raise NotImplementedError("save_tool not implemented")

    @expose_sync_method("get_tool")
    async def get_tool_async(self, tool_id: str) -> Optional[Tool]:
        raise NotImplementedError("get_tool not implemented")

    @expose_sync_method("list_tools")
    async def list_tools_async(
        self, filter_params: Optional[dict] = None
    ) -> List[Tool]:
        raise NotImplementedError("list_tools not implemented")


class InMemoryToolStore(BaseToolStore):
    def __init__(self):
        self.tools = {}

    @expose_sync_method("save_tool")
    async def save_tool_async(self, tool: Tool) -> None:
        self.tools[tool.id] = tool

    @expose_sync_method("get_tool")
    async def get_tool_async(self, tool_id: str) -> Optional[Tool]:
        return self.tools.get(tool_id)

    @expose_sync_method("list_tools")
    async def list_tools_async(
        self, filter_params: Optional[dict] = None
    ) -> List[Tool]:
        if not filter_params:
            return list(self.tools.values())
        return [
            tool
            for tool in self.tools.values()
            if all(getattr(tool, k, None) == v for k, v in filter_params.items())
        ]


class DjangoToolStore(BaseToolStore):
    def __init__(self, model):
        self.model = model

    @expose_sync_method("save_tool")
    async def save_tool_async(self, tool: Tool) -> None:
        await self.model.objects.update_or_create(
            id=tool.id, defaults=tool.model_dump()
        )

    @expose_sync_method("get_tool")
    async def get_tool_async(self, tool_id: str) -> Optional[Tool]:
        tool = await self.model.objects.filter(id=tool_id).first()
        return Tool.model_validate(tool) if tool else None

    @expose_sync_method("list_tools")
    async def list_tools_async(
        self, filter_params: Optional[dict] = None
    ) -> List[Tool]:
        queryset = self.model.objects.all()
        if filter_params:
            queryset = queryset.filter(**filter_params)
        tools = await queryset
        return [Tool.model_validate(tool) for tool in tools]


class RedisToolStore(BaseToolStore, RedisBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect()

    @expose_sync_method("save_tool")
    async def save_tool_async(self, tool: Tool) -> None:
        self.redis_client.set(f"tool:{tool.id}", tool.model_dump_json())

    @expose_sync_method("get_tool")
    async def get_tool_async(self, tool_id: str) -> Optional[Tool]:
        tool_data = self.redis_client.get(f"tool:{tool_id}")
        return Tool.model_validate_json(tool_data) if tool_data else None

    @expose_sync_method("list_tools")
    async def list_tools_async(
        self, filter_params: Optional[dict] = None
    ) -> List[Tool]:
        all_tools = [
            Tool.model_validate_json(tool_data)
            for tool_data in self.redis_client.mget(self.redis_client.keys("tool:*"))
        ]
        if not filter_params:
            return all_tools
        return [
            tool
            for tool in all_tools
            if all(getattr(tool, k, None) == v for k, v in filter_params.items())
        ]
