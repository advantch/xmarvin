import uuid
from contextlib import asynccontextmanager, contextmanager

from marvin.extensions.context.run_context import (
    RunContext,
    RunContextStores,
    add_run_context,
    clear_run_context,
)
from marvin.extensions.context.tenant import get_current_tenant_id
from marvin.extensions.storage.run_store import BaseRunStore, InMemoryRunStore
from marvin.extensions.types.run import PersistedRun


@contextmanager
def tool_run_context(
    tool_id: str,
    config: dict,
    input_data: dict,
    toolkit_id: str | uuid.UUID | None = None,
    db_id: str | uuid.UUID | None = None,
    run_store_class: BaseRunStore | None = InMemoryRunStore,
):
    run_id = str(uuid.uuid4())
    tenant_id = get_current_tenant_id()

    run_store = run_store_class() or InMemoryRunStore()

    # Create run object in the database
    persisted_run = PersistedRun(
        id=run_id,
        tenant_id=tenant_id,
        data={
            "tool_id": tool_id,
            "config": config,
            "input_data": input_data,
            "db_id": db_id,
            "toolkit_id": toolkit_id,
        },
    )
    run_store.save_run(persisted_run)

    # Create run context
    context = RunContext(
        run_id=run_id,
        tenant_id=tenant_id,
        tool_config=[
            {
                "tool_id": tool_id,
                "config": config,
                "name": tool_id,
                "toolkit_id": toolkit_id,
            }
        ],
        stores=RunContextStores(run_store=run_store),
    )

    _c = context.model_dump()
    # Add run context
    add_run_context(_c, run_id)

    try:
        yield persisted_run, _c
    except Exception as e:
        persisted_run.status = "failed"
        run_store.save_run(persisted_run)
        raise e
    finally:
        # Update run status
        persisted_run.status = "completed"
        run_store.save_run(persisted_run)
        clear_run_context(run_id)


@asynccontextmanager
async def async_tool_run_context(
    tool_id: str,
    config: dict,
    input_data: dict,
    toolkit_id: str | uuid.UUID | None = None,
    db_id: str | uuid.UUID | None = None,
    run_store_class: BaseRunStore | None = InMemoryRunStore,
):
    run_id = str(uuid.uuid4())
    tenant_id = get_current_tenant_id()

    run_store = run_store_class() or InMemoryRunStore()

    # Create run object in the database
    persisted_run = PersistedRun(
        id=run_id,
        tenant_id=tenant_id,
        data={
            "tool_id": tool_id,
            "config": config,
            "input_data": input_data,
            "db_id": db_id,
            "toolkit_id": toolkit_id,
        },
    )
    await run_store.save_async(persisted_run)

    # Create run context
    context = RunContext(
        run_id=run_id,
        tenant_id=tenant_id,
        tool_config=[
            {
                "tool_id": tool_id,
                "config": config,
                "name": tool_id,
                "toolkit_id": toolkit_id,
            }
        ],
        stores=RunContextStores(run_store=run_store),
    )

    _c = context.model_dump()
    # Add run context
    add_run_context(_c, run_id)

    try:
        yield persisted_run, _c
    except Exception as e:
        persisted_run.status = "failed"
        await run_store.save_async(persisted_run)
        raise e
    finally:
        # Update run status
        persisted_run.status = "completed"
        await run_store.save_async(persisted_run)
        clear_run_context(run_id)
