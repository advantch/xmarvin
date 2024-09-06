import uuid
from contextlib import contextmanager

from marvin.extensions.context.run_context import (
    RunContext,
    add_run_context,
    clear_run_context,
)
from marvin.extensions.context.tenant import get_current_tenant_id
from marvin.extensions.storage.base import BaseRunStorage
from marvin.extensions.storage.stores import RunStore
from marvin.extensions.types.run import PersistedRun


@contextmanager
def tool_run_context(
    tool_id: str,
    config: dict,
    input_data: dict,
    toolkit_id: str | uuid.UUID | None = None,
    db_id: str | uuid.UUID | None = None,
    run_storage_class: BaseRunStorage | None = RunStore,
):
    run_id = str(uuid.uuid4())
    tenant_id = get_current_tenant_id()

    run_storage = run_storage_class() or RunStore()

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
    run_storage.create(persisted_run)

    # Create run context
    context = RunContext(
        run_id=run_id,
        tenant_id=tenant_id,
        tool_id=tool_id,
        tool_config=[
            {
                "tool_id": tool_id,
                "config": config,
                "name": tool_id,
                "toolkit_id": toolkit_id,
            }
        ],
    )

    _c = context.model_dump()
    # Add run context
    add_run_context(_c, run_id)

    try:
        yield persisted_run, _c
    except Exception as e:
        persisted_run.status = "failed"
        run_storage.update(persisted_run)
        raise e
    finally:
        # Update run status
        persisted_run.status = "completed"
        run_storage.update(persisted_run)
        clear_run_context(run_id)
