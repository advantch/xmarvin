import contextvars
from contextlib import asynccontextmanager
from uuid import UUID

# Context variables
_tenant_id = contextvars.ContextVar("tenant_id", default=None)
_tenant_metadata = contextvars.ContextVar("tenant_metadata", default={})
_tenant_state = contextvars.ContextVar("tenant_state", default={})


def get_current_tenant_id() -> str | None:
    return _tenant_id.get()


def set_current_tenant_id(tenant_id: str | UUID | None) -> None:
    if not tenant_id:
        _tenant_id.set(None)
    elif isinstance(tenant_id, UUID):
        _tenant_id.set(str(tenant_id))
    else:
        _tenant_id.set(tenant_id)


def set_tenant_metadata(metadata: dict) -> None:
    _tenant_metadata.set(metadata)


def get_tenant_metadata() -> dict:
    return _tenant_metadata.get()


def set_tenant_from_current_thread():
    # This function doesn't need to change as it uses get_current_tenant_id
    tenant_id = get_current_tenant_id()
    set_current_tenant_id(tenant_id)


def unset_current_tenant_id() -> None:
    _tenant_id.set(None)


@asynccontextmanager
async def tenant_context(tenant_id):
    token = _tenant_id.set(tenant_id)
    try:
        yield
    finally:
        _tenant_id.reset(token)


@asynccontextmanager
async def empty_tenant_context():
    token = _tenant_id.set(None)
    try:
        yield
    finally:
        _tenant_id.reset(token)


def default_tenant_dns_settings():
    return {
        "cloudflare": {},
        "has_dns": False,
        "selfhosted": False,
    }


def set_thread_state(tenant_id: str, data: dict):
    current_state = _tenant_state.get()
    current_state[tenant_id] = data
    _tenant_state.set(current_state)


def clear_thread_state(tenant_id: str):
    current_state = _tenant_state.get()
    current_state.pop(tenant_id, None)
    _tenant_state.set(current_state)
