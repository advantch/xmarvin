"""Global thread safe state for storing context during request processing."""

from typing import Any

from asgiref.local import Local

_async_local = Local()


def set_context(key: str, value: Any, container: Local | None = None):
    """Set global context."""
    if container is None:
        container = _async_local
    container[key] = value


def get_context(key: str, container: Local | None = None) -> Any:
    """Get global context."""
    if container is None:
        container = _async_local
    return container[key]


def get_global_container() -> Local:
    return _async_local
