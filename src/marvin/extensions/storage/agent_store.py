from typing import List, Optional

from marvin.extensions.storage.base import BaseStorage
from marvin.extensions.storage.redis_base import RedisBase
from marvin.extensions.types import AgentConfig


class BaseAgentStore(BaseStorage[AgentConfig]):
    async def save_async(self, agent: AgentConfig) -> None:
        raise NotImplementedError("save_async not implemented")

    async def get_async(self, agent_id: str) -> Optional[AgentConfig]:
        raise NotImplementedError("get_async not implemented")

    async def list_async(
        self, filter_params: Optional[dict] = None
    ) -> List[AgentConfig]:
        raise NotImplementedError("list_async not implemented")


class InMemoryAgentStore(BaseAgentStore):
    def __init__(self):
        self.agents = {}

    async def save_async(self, agent: AgentConfig) -> None:
        self.agents[agent.id] = agent

    async def get_async(self, agent_id: str) -> Optional[AgentConfig]:
        return self.agents.get(agent_id)

    async def list_async(
        self, filter_params: Optional[dict] = None
    ) -> List[AgentConfig]:
        if not filter_params:
            return list(self.agents.values())
        return [
            agent
            for agent in self.agents.values()
            if all(getattr(agent, k, None) == v for k, v in filter_params.items())
        ]


class DjangoAgentStore(BaseAgentStore):
    def __init__(self, model):
        self.model = model

    async def save_async(self, agent: AgentConfig) -> None:
        await self.model.objects.aupdate_or_create(
            id=agent.id, defaults=agent.model_dump()
        )

    async def get_async(self, agent_id: str) -> Optional[AgentConfig]:
        agent = await self.model.objects.filter(id=agent_id).afirst()
        return AgentConfig.model_validate(agent) if agent else None

    async def list_async(
        self, filter_params: Optional[dict] = None
    ) -> List[AgentConfig]:
        queryset = self.model.objects.all()
        if filter_params:
            queryset = queryset.filter(**filter_params)
        agents = await queryset
        return [AgentConfig.model_validate(agent) for agent in agents]


class RedisAgentStore(BaseAgentStore, RedisBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect()

    async def save_async(self, agent: AgentConfig) -> None:
        await self.redis_client.set(f"agent:{agent.id}", agent.model_dump_json())

    async def get_async(self, agent_id: str) -> Optional[AgentConfig]:
        agent_data = await self.redis_client.get(f"agent:{agent_id}")
        return AgentConfig.model_validate_json(agent_data) if agent_data else None

    async def list_async(
        self, filter_params: Optional[dict] = None
    ) -> List[AgentConfig]:
        all_agents = [
            AgentConfig.model_validate_json(agent_data)
            for agent_data in await self.redis_client.mget(
                await self.redis_client.keys("agent:*")
            )
        ]
        if not filter_params:
            return all_agents
        return [
            agent
            for agent in all_agents
            if all(getattr(agent, k, None) == v for k, v in filter_params.items())
        ]
