import uuid
from typing import Any, List

from asgiref.local import Local
from pydantic import BaseModel, Field

_async_local = Local()
_async_local.ctx = {}


class RunContextToolkitConfig(BaseModel):
    toolkit_id: str | uuid.UUID | None = None
    db_id: str | uuid.UUID | None = None
    config: dict | None = None


class RunContext(BaseModel):
    """
    Runtime context for tools, agents and other components.

    Every run is associated with a context.
    Runs are triggered within a context manager which exposes the context to the run.
    """

    channel_id: str | uuid.UUID | None = None
    run_id: str | uuid.UUID | None = None
    thread_id: str | uuid.UUID | None = None
    tenant_id: str | uuid.UUID | None = None
    data_sources: List[str] | None = None
    agent_config: Any | None = None
    variables: dict[str, dict] | None = None
    tool_config: List[RunContextToolkitConfig] | None = Field(
        default_factory=list,
        description="The configuration for the tools to be used in the run.",
    )
    private_ref: str | None = Field(
        default=None,
        description="Private reference for the run can be the tool id or agent id.",
    )
    meta: dict[str, Any] | None = None
    storage: dict[str, Any] = {
        "tool_calls": [],
        "errors": [],
        "messages": [],
        "run_metadata": {},
        "tool_outputs": [],
    }

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True


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
