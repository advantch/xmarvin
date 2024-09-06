from contextlib import asynccontextmanager
from uuid import UUID

from marvin.extensions.settings import extension_settings

_async_local = extension_settings.app_context.container()
_async_local.tenant_id = None
_async_local.tenant_metadata = {}
_async_local.tenant_state = {}


def get_current_tenant_id() -> str | None:
    return _async_local.tenant_id


def set_current_tenant_id(tenant_id: str | UUID | None) -> None:
    if not tenant_id:
        _async_local.tenant_id = None
    elif isinstance(tenant_id, UUID):
        _async_local.tenant_id = str(tenant_id)
    else:
        _async_local.tenant_id = tenant_id


def set_tenant_metadata(metadata: dict) -> None:
    _async_local.tenant_metadata = metadata


def get_tenant_metadata() -> dict:
    return _async_local.tenant_metadata


def unset_current_tenant_id() -> None:
    _async_local.tenant_id = None


def set_thread_state(tenant_id: str, data: dict):
    _async_local.tenant_state[tenant_id] = data


def clear_thread_state(tenant_id: str):
    _async_local.tenant_state.pop(tenant_id, None)


@asynccontextmanager
async def tenant_context(tenant_id):
    previous_tenant_id = _async_local.tenant_id
    _async_local.tenant_id = tenant_id
    try:
        yield
    finally:
        _async_local.tenant_id = previous_tenant_id


@asynccontextmanager
async def empty_tenant_context():
    previous_tenant_id = _async_local.tenant_id
    _async_local.tenant_id = None
    try:
        yield
    finally:
        _async_local.tenant_id = previous_tenant_id


# Existing functions that don't need changes
def set_tenant_from_current_thread():
    tenant_id = get_current_tenant_id()
    set_current_tenant_id(tenant_id)
