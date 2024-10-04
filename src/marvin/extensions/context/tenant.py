"""
This module provides a global context for storing and retrieving tenant-specific data.
It uses the `asgiref.local.Local` class to store the context in a thread-local manner.

In advantch apps we already use this for managing tenant state across threads.
Make sure to set this app at the start of the app.
"""

from contextlib import asynccontextmanager
from uuid import UUID

from asgiref.local import Local

from marvin.extensions.settings import extension_settings

state = None
# check if is advantch and import from there
try:
    from apps.common.tenants import _async_local as state
except ImportError:
    state = extension_settings.global_context.container()

_async_local: Local = state


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
