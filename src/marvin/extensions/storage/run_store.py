from typing import Any, List, Optional, Tuple

from marvin.extensions.storage.base import BaseStorage
from marvin.extensions.storage.redis_base import RedisBase
from marvin.extensions.types import PersistedRun
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method


class BaseRunStore(BaseStorage[PersistedRun], ExposeSyncMethodsMixin):
    """
    Interface for run storage classes.
    """

    @expose_sync_method("save_run")
    async def save_run_async(self, run: PersistedRun) -> None:
        raise NotImplementedError("save_run not implemented")

    @expose_sync_method("get_run")
    async def get_run_async(self, run_id: str) -> Optional[PersistedRun]:
        raise NotImplementedError("get_run not implemented")

    @expose_sync_method("list_runs")
    async def list_runs_async(
        self, filter_params: Optional[dict] = None
    ) -> List[PersistedRun]:
        raise NotImplementedError("list_runs not implemented")

    @expose_sync_method("get_or_create")
    async def get_or_create_async(self, id: str) -> Tuple[PersistedRun, bool]:
        raise NotImplementedError("get_or_create not implemented")

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
        raise NotImplementedError("init_db_run not implemented")


class InMemoryRunStore(BaseRunStore):
    def __init__(self):
        self.runs = {}

    @expose_sync_method("save_run")
    async def save_run_async(self, run: PersistedRun) -> None:
        self.runs[run.id] = run

    @expose_sync_method("get_run")
    async def get_run_async(self, run_id: str) -> Optional[PersistedRun]:
        return self.runs.get(run_id)

    @expose_sync_method("list_runs")
    async def list_runs_async(
        self, filter_params: Optional[dict] = None
    ) -> List[PersistedRun]:
        if not filter_params:
            return list(self.runs.values())
        return [
            run
            for run in self.runs.values()
            if all(getattr(run, k, None) == v for k, v in filter_params.items())
        ]

    @expose_sync_method("get_or_create")
    async def get_or_create_async(self, id: str) -> Tuple[PersistedRun, bool]:
        run = self.runs.get(id)
        if run:
            return run, False
        run = PersistedRun(id=id)
        self.runs[id] = run
        return run, True

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
        run, created = await self.get_or_create_async(run_id)
        if created:
            run.thread_id = thread_id
            run.tenant_id = tenant_id
            run.agent_id = agent_id
            run.status = "started"
            if user_message:
                run.data["user_message"] = user_message
            if tags:
                run.tags = tags
        if remote_run:
            run.external_id = remote_run.id
        await self.save_run_async(run)
        return run


class DjangoRunStore(BaseRunStore):
    def __init__(self, model):
        self.model = model

    @expose_sync_method("save_run")
    async def save_run_async(self, run: PersistedRun) -> None:
        await self.model.objects.update_or_create(id=run.id, defaults=run.model_dump())

    @expose_sync_method("get_run")
    async def get_run_async(self, run_id: str) -> Optional[PersistedRun]:
        run = await self.model.objects.filter(id=run_id).first()
        return PersistedRun.model_validate(run) if run else None

    @expose_sync_method("list_runs")
    async def list_runs_async(
        self, filter_params: Optional[dict] = None
    ) -> List[PersistedRun]:
        queryset = self.model.objects.all()
        if filter_params:
            queryset = queryset.filter(**filter_params)
        runs = await queryset
        return [PersistedRun.model_validate(run) for run in runs]

    @expose_sync_method("get_or_create")
    async def get_or_create_async(self, id: str) -> Tuple[PersistedRun, bool]:
        run, created = await self.model.objects.get_or_create(id=id)
        return PersistedRun.model_validate(run), created

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
        run, created = await self.get_or_create_async(run_id)
        if created:
            run.thread_id = thread_id
            run.tenant_id = tenant_id
            run.agent_id = agent_id
            run.status = "started"
            if user_message:
                run.data["user_message"] = user_message
            if tags:
                run.tags = tags
        if remote_run:
            run.external_id = remote_run.id
        await self.save_run_async(run)
        return run


class RedisRunStore(BaseRunStore, RedisBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect()

    @expose_sync_method("save_run")
    async def save_run_async(self, run: PersistedRun) -> None:
        self.redis_client.set(f"run:{run.id}", run.model_dump_json())

    @expose_sync_method("get_run")
    async def get_run_async(self, run_id: str) -> Optional[PersistedRun]:
        run_data = self.redis_client.get(f"run:{run_id}")
        return PersistedRun.model_validate_json(run_data) if run_data else None

    @expose_sync_method("list_runs")
    async def list_runs_async(
        self, filter_params: Optional[dict] = None
    ) -> List[PersistedRun]:
        all_runs = [
            PersistedRun.model_validate_json(run_data)
            for run_data in self.redis_client.mget(self.redis_client.keys("run:*"))
        ]
        if not filter_params:
            return all_runs
        return [
            run
            for run in all_runs
            if all(getattr(run, k, None) == v for k, v in filter_params.items())
        ]

    @expose_sync_method("get_or_create")
    async def get_or_create_async(self, id: str) -> Tuple[PersistedRun, bool]:
        run_data = self.redis_client.get(f"run:{id}")
        if run_data:
            return PersistedRun.model_validate_json(run_data), False
        run = PersistedRun(id=id)
        await self.save_run_async(run)
        return run, True

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
        run, created = await self.get_or_create_async(run_id)
        if created:
            run.thread_id = thread_id
            run.tenant_id = tenant_id
            run.agent_id = agent_id
            run.status = "started"
            if user_message:
                run.data["user_message"] = user_message
            if tags:
                run.tags = tags
        if remote_run:
            run.external_id = remote_run.id
        await self.save_run_async(run)
        return run
