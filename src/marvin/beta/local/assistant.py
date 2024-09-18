import uuid
from typing import List, Optional

from pydantic import BaseModel, Field

from marvin.extensions.storage import BaseChatStore
from marvin.extensions.tools.tool import Tool
from marvin.extensions.types.agent import AgentConfig
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, run_sync


class LocalAssistant(BaseModel, ExposeSyncMethodsMixin):
    id: str | None | uuid.UUID = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str | None = None
    instructions: str | None = None
    tools: List[Tool] | None = Field(default_factory=list)
    model: str | None = None
    file_ids: List[str] | None = Field(default_factory=list)
    vector_store_id: str | None = None
    storage: Optional[type[BaseChatStore]] = None

    def run(self, thread, **kwargs):
        from .run import LocalRun  # noqa: F401

        return LocalRun(assistant=self, thread=thread, **kwargs)

    @classmethod
    def from_agent_config(cls, agent_config: AgentConfig):
        return cls(
            id=agent_config.id or str(uuid.uuid4()),
            name=agent_config.name,
            instructions=agent_config.get_instructions(),
            tools=agent_config.get_tools(),
            model=agent_config.model,
            file_ids=agent_config.file_ids,
            vector_store_id=agent_config.vector_store_id,
        )

    @classmethod
    async def from_agent_config_async(cls, agent_config):
        return await run_sync(cls.from_agent_config)(agent_config)
