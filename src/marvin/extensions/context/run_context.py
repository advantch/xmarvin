import uuid
from contextlib import contextmanager
from typing import Any, List

from asgiref.local import Local
from pydantic import BaseModel, ConfigDict, Field

from marvin.extensions.cache.cache import mem_cache
from marvin.extensions.context.tenant import set_current_tenant_id
from marvin.extensions.file_storage.base import BaseBlobStorage
from marvin.extensions.memory.runtime_memory import RuntimeMemory
from marvin.extensions.storage import (
    BaseAgentStore,
    BaseDataSourceStore,
    BaseMessageStore,
    BaseRunStore,
    BaseThreadStore,
    BaseToolStore,
)

from .scoped_context import ctx

_async_local = Local()
_async_local.ctx = {}


class RunContextToolkitConfig(BaseModel):
    toolkit_id: str | uuid.UUID | None = None
    db_id: str | uuid.UUID | None = None
    config: dict | None = None


class RunContextStores(BaseModel):
    """
    Storages for the run context.
    """

    thread_store: BaseThreadStore | None = None
    tool_store: BaseToolStore | None = None
    data_source_store: BaseDataSourceStore | None = None
    agent_store: BaseAgentStore | None = None
    run_store: BaseRunStore | None = None
    message_store: BaseMessageStore | None = None
    file_storage: BaseBlobStorage | None = None
    model_config = dict(arbitrary_types_allowed=True)


class RunContextCache(BaseModel):
    """
    Stores for the run context.
    """

    tool_calls: List[Any] = Field(default_factory=list)
    errors: List[Any] = Field(default_factory=list)
    messages: List[Any] = Field(default_factory=list)
    run_metadata: dict = Field(default_factory=dict)
    tool_outputs: List[Any] = Field(default_factory=list)
    generated_files: List[Any] = Field(default_factory=list)
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")


class RunContext(BaseModel):
    """
    Runtime context for tools, agents and other components.

    Every run has an associated context.
    Context is passed to the run and can be used to store data for the run.

    The context can be retrieved at any point in time using the `get_run_context` function.
    This requires that the run be triggered with a context manager.
    """

    channel_id: str | uuid.UUID | None = Field(
        default=None,
        description="The id of the channel. If supplied any messages will be sent to the channel.",
    )
    run_id: str | uuid.UUID | None = Field(
        default=None, description="The id of the run."
    )

    thread_id: str | uuid.UUID | None = Field(
        default=None, description="The id of the thread."
    )
    tenant_id: str | uuid.UUID | None = Field(
        default="default", description="The id of the tenant."
    )
    data_sources: List[str] | None = Field(
        default=None, description="The data sources for the run."
    )
    agent_config: Any | None = Field(
        default=None, description="The configuration for the agent."
    )
    variables: dict[str, dict] | None = Field(
        default=None, description="The variables for the run."
    )
    tool_config: List[RunContextToolkitConfig] | None = Field(
        default_factory=list,
        description="The configuration for the tools to be used in the run.",
    )
    runtime_memory: RuntimeMemory | None = Field(
        default=None, description="The runtime memory for the run."
    )
    private_ref: str | None = Field(
        default=None,
        description="Private reference for the run can be the tool id or agent id.",
    )
    meta: dict[str, Any] | None = None
    stores: RunContextStores = Field(
        ..., description="The stores for the run. This is require"
    )
    cache: RunContextCache = Field(default_factory=RunContextCache)
    context_dict: dict = Field(
        default_factory=dict, description="The original context dict."
    )

    cache_store: Any = Field(
        default=mem_cache,
        description="The cache store for the run. You can replace this with redis or other storage",
    )

    _cm_stack: list[contextmanager] = []

    class Config:
        extra = "forbid"
        arbitrary_types_allowed = True

    def __enter__(self):
        # check run created
        persisted_run = self.stores.run_store.get_run(self.run_id)
        if not persisted_run:
            raise ValueError(f"Run {self.run_id} not found.")
        cm = self.create_context()
        self._cm_stack.append(cm)
        add_run_context(self.model_dump(), self.run_id)
        set_current_tenant_id(self.tenant_id)
        return cm.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is not None:
                # Handle exception if needed
                self.cache.errors.append(str(exc_value))
                # Update run status to 'failed' if needed
                if self.stores and self.stores.run_store:
                    persisted_run = self.stores.run_store.get_run(self.run_id)
                    if persisted_run:
                        persisted_run.status = "failed"
                        self.stores.run_store.save_run(persisted_run)
            else:
                # Update run status to 'completed' if not failed
                if self.stores and self.stores.run_store:
                    persisted_run = self.stores.run_store.get_run(self.run_id)
                    if persisted_run and persisted_run.status != "failed":
                        persisted_run.status = "completed"
                        self.stores.run_store.save_run(persisted_run)

            # Save run context data
            if self.stores and self.stores.run_store:
                persisted_run = self.stores.run_store.get_run(self.run_id)
                if persisted_run:
                    persisted_run.save_run_context_data(self)
                    self.stores.run_store.save_run(persisted_run)

        finally:
            clear_run_context(self.run_id)
            ctx.set(run=None)
            self._cm_stack.pop().__exit__(exc_type, exc_value, traceback)

    @contextmanager
    def create_context(self, **run_kwargs) -> "RunContext":
        """
        Create a run context.
        """
        self.context_dict = self.model_dump()
        with ctx(run=self):
            yield self


def add_run_context(context: dict, run_id: str):
    """Add context to thread."""
    set_current_run_id(run_id)

    if not hasattr(_async_local, "run_context"):
        _async_local.run_context = {}
    _async_local.run_context[run_id] = context


def get_run_context(
    run_id: str | None = None, as_class=False
) -> dict | RunContext | None:
    """Get context from thread."""
    run_id = run_id or get_current_run_id()
    if run_id is None:
        return None

    if not hasattr(_async_local, "run_context"):
        _async_local.run_context = {}
    c = _async_local.run_context.get(run_id, {})
    if as_class:
        return RunContext(**c)
    return c


def get_current_run_id() -> str | None:
    """Get current run id."""
    if not hasattr(_async_local, "run_id"):
        return None
    return _async_local.run_id


def set_current_run_id(run_id: str):
    """Set current run id."""
    if not hasattr(_async_local, "run_id"):
        _async_local.run_id = None
    _async_local.run_id = run_id


def clear_run_context(run_id: str):
    """Clear run context."""
    if hasattr(_async_local, "run_context"):
        del _async_local.run_context[run_id]
    if hasattr(_async_local, "run_id") and _async_local.run_id == run_id:
        del _async_local.run_id


def get_global_context() -> dict:
    """Get global context."""
    return _async_local.ctx


def get_current_run() -> RunContext:
    try:
        return ctx.get("run")
    except KeyError:
        raise ValueError(
            "No run context found."
            " Did you trigger the run with a context manager?"
            "use 'with RunContext(**run_kwargs) as run:'"
        )
