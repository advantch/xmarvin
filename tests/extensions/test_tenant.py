# Test
import asyncio
import pytest

from marvin.extensions.utilities.tenant import (
    tenant_context,
    empty_tenant_context,
    set_tenant_metadata,
    get_tenant_metadata,
    set_thread_state,
    clear_thread_state,
    _tenant_state,
    _tenant_metadata,
    get_current_tenant_id,
    set_current_tenant_id,
)

@pytest.mark.asyncio
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
    assert _tenant_state.get()["tenant4"] == {"data": "test"}
    clear_thread_state("tenant4")
    assert "tenant4" not in _tenant_state.get()

    print("All tests passed!")

# Run the test
asyncio.run(test_tenant_context())