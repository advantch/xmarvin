import pytest

from marvin.extensions.context.tenant import (
    clear_thread_state,
    empty_tenant_context,
    get_current_tenant_id,
    get_tenant_metadata,
    set_current_tenant_id,
    set_tenant_metadata,
    set_thread_state,
    tenant_context,
)


@pytest.mark.asyncio
@pytest.mark.no_llm
async def test_tenant_context():
    async def check_tenant(expected_id):
        assert get_current_tenant_id() == expected_id

    # Test tenant_context
    async with tenant_context("tenant1"):
        await check_tenant("tenant1")
        async with tenant_context("tenant2"):
            await check_tenant("tenant2")
        await check_tenant("tenant1")

    # Test empty_tenant_context
    set_current_tenant_id("tenant3")
    async with empty_tenant_context():
        await check_tenant(None)
    await check_tenant("tenant3")

    # Test set_tenant_metadata and get_tenant_metadata
    set_tenant_metadata({"key": "value"})
    assert get_tenant_metadata() == {"key": "value"}

    # Test set_thread_state and clear_thread_state
    set_thread_state("tenant4", {"data": "test"})
