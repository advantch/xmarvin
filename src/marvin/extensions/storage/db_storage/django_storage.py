from typing import Any, Dict, List, Optional
from uuid import UUID

from marvin.extensions.tools.tool_kit import Toolkit
from marvin.extensions.types.agent import AgentConfig
from marvin.extensions.types.run import PersistedRun
import orjson
from pydantic import Field

from marvin.extensions.storage.base import (
    BaseAgentStorage,
    BaseChatStore,
    BaseRunStorage,
    BaseThreadStore,
    BaseToolkitStorage,
)
from marvin.extensions.types import ChatMessage
from marvin.utilities.asyncio import expose_sync_method
from marvin.utilities.logging import logger


class DJangoDBChatStore(BaseChatStore):
    """Database chat store."""

    store: Dict[str, List[ChatMessage]] = Field(default_factory=dict)
    run_id: Optional[str | UUID] = None
    thread_id: Optional[str | UUID] = None
    tenant_id: Optional[str | UUID] = None
    django_message_model: Optional[Any] = None

    class Config:
        allow_extra = True
        arbitrary_types_allowed = True
        extra = "allow"

    def __str__(self):
        return f"DbChatStore(thread_id={self.thread_id}, run_id={self.run_id}, tenant_id={self.tenant_id})"

    @classmethod
    def class_name(cls) -> str:
        """Get class name."""
        return "DBChatStore"

    @expose_sync_method("set_messages")
    async def set_messages_async(self, key: str, messages: List[ChatMessage]) -> None:
        """Set messages for a key."""
        await self.django_message_model.objects.acreate_many(
            messages,
            thread_id=self.thread_id,
            run_id=self.run_id,
            tenant_id=self.tenant_id,
        )

    @expose_sync_method("get_messages")
    async def get_messages_async(self, key: str, **kwargs) -> List[ChatMessage]:
        """Get messages for a key."""
        messages = (
            self.django_message_model.objects.filter(thread_id=self.thread_id)
            .order_by("created")
            .all()
        )
        message_dicts = []
        async for message in messages:
            message_dicts.append(message.message)
        return [ChatMessage.model_validate(m) for m in message_dicts]

    @expose_sync_method("add_message")
    async def add_message_async(
        self, key: str, message: ChatMessage, idx: Optional[int] = None
    ) -> None:
        """Add a message for a key."""
        try:
            await self.django_message_model.objects.acreate_or_update(
                data=orjson.loads(message.model_dump_json()),
                thread_id=self.thread_id,
                tenant_id=self.tenant_id,
                run_id=self.run_id,
            )
        except Exception as e:
            logger.error(f"Error adding message to store: {e}")

    async def delete_messages_async(self, key: str, **kwargs) -> None:
        """Delete messages for a key."""
        message = await self.django_message_model.objects.filter(
            thread_id=self.thread_id, run_id=self.run_id
        ).afirst()
        if message:
            await message.adelete()
        return None

    async def delete_message_async(self, key: str, idx: int) -> Optional[ChatMessage]:
        """Delete specific message for a key."""
        if key not in self.store:
            return None
        if idx >= len(self.store[key]):
            return None
        return self.store[key].pop(idx)

    async def delete_last_message_async(self, key: str) -> Optional[ChatMessage]:
        """Delete last message for a key."""
        messages = await self.django_message_model.objects.filter(
            thread_id=self.thread_id, run_id=self.run_id
        ).aget()
        if not messages:
            return None
        message = messages[-1]
        await self.django_message_model.objects.adelete(message)
        return message

    async def get_keys_async(self) -> List[str]:
        """Get all keys."""
        return [self.thread_id]


class DJangoDBThreadStore(BaseThreadStore):
    """
    Thread storage that saves to the database.
    """

    django_chat_model: Optional[Any] = None

    @expose_sync_method("get_or_add_thread")
    async def get_or_add_thread_async(
        self,
        thread_id: str,
        tenant_id: str,
        tags: List[str] | None = None,
        name: str | None = None,
        user_id: str | None = None,
    ) -> "DJangoDBThreadStore":
        thread = await self.django_chat_model.objects.aget_or_add_thread(
            thread_id, tenant_id=tenant_id, tags=tags, name=name, user_id=user_id
        )
        return thread


class DJangoDBRunStore(BaseRunStorage):
    """Database run storage."""

    django_run_model: Optional[Any] = None
    tenant_id: Optional[str | UUID] = None

    class Config:
        arbitrary_types_allowed = True

    @expose_sync_method("get_or_create")
    async def get_or_create_async(self, id: str) -> tuple[PersistedRun, bool]:
        """Get or create a run."""
        run, created = await self.django_run_model.objects.aget_or_create(
            id=id,
            defaults={'tenant_id': self.tenant_id}
        )
        return run, created

    @expose_sync_method("init_db_run")
    async def init_db_run_async(
        self,
        run_id: str,
        thread_id: str | None = None,
        tenant_id: str | None = None,
        remote_run: Any = None,
        agent_id: str | None = None,
        user_message: str | None = None,
        tags: List[str] | None = None,
    ) -> PersistedRun:
        """Initialize a database run."""
        run, created = await self.get_or_create_async(run_id)
        if created:
            run.thread_id = thread_id
            run.tenant_id = tenant_id
            run.agent_id = agent_id
            run.status = "started"
            if user_message:
                run.data["user_message"] = user_message
            if tags:
                run.tags.set(tags)
            await run.asave()
        if remote_run:
            run.external_id = remote_run.id
            await run.asave()
        return run

class DJangoDBAgentStore(BaseAgentStorage):
    """Database agent storage."""

    django_agent_model: Optional[Any] = None
    tenant_id: Optional[str | UUID] = None

    class Config:
        arbitrary_types_allowed = True

    @expose_sync_method("create")
    async def create_async(self, key: str, value: AgentConfig) -> None:
        """Create an agent."""
        await self.django_agent_model.objects.acreate(
            id=key,
            config=value.model_dump(),
            tenant_id=self.tenant_id
        )

    @expose_sync_method("get")
    async def get_async(self, key: str) -> Optional[AgentConfig]:
        """Get an agent by key."""
        agent = await self.django_agent_model.objects.filter(id=key).afirst()
        if agent:
            return AgentConfig(**agent.config)
        return None

    @expose_sync_method("update")
    async def update_async(self, key: str, value: AgentConfig) -> AgentConfig:
        """Update an agent."""
        await self.django_agent_model.objects.filter(id=key).aupdate(config=value.model_dump())
        return value

    @expose_sync_method("list")
    async def list_async(self, **filters) -> List[AgentConfig]:
        """List agents."""
        agents = await self.django_agent_model.objects.filter(**filters).all()
        return [AgentConfig(**agent.config) for agent in agents]

class DJangoDBToolkitStore(BaseToolkitStorage):
    """Database toolkit storage."""

    django_toolkit_model: Optional[Any] = None
    tenant_id: Optional[str | UUID] = None

    class Config:
        arbitrary_types_allowed = True

    @expose_sync_method("create")
    async def create_async(self, key: str, value: Toolkit) -> None:
        """Create a tool."""
        await self.django_tool_model.objects.acreate(
            id=key,
            config=value.model_dump(),
            tenant_id=self.tenant_id
        )

    @expose_sync_method("get")
    async def get_async(self, key: str) -> Optional[Toolkit]:
        """Get a tool by key."""
        tool = await self.django_tool_model.objects.filter(id=key).afirst()
        if tool:
            return Toolkit(**tool.config)
        return None

    @expose_sync_method("update")
    async def update_async(self, key: str, value: Toolkit) -> Toolkit:
        """Update a tool."""
        await self.django_tool_model.objects.filter(id=key).aupdate(config=value.model_dump())
        return value

    @expose_sync_method("list")
    async def list_async(self, **filters) -> List[Toolkit]:
        """List tools."""
        tools = await self.django_tool_model.objects.filter(**filters).all()
        return [Toolkit(**tool.config) for tool in tools]