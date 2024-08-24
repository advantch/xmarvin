import uuid
from contextlib import contextmanager

from apps.ai.models import Run
from apps.tenants.utils import get_current_tenant_id

from marvin.extensions.utilities.context import (
    RunContext,
    add_run_context,
    clear_run_context,
)


@contextmanager
def tool_run_context(
    tool_id: str, 
    config: dict, 
    input_data: dict, 
    toolkit_id: str | uuid.UUID | None = None,
    db_id: str | uuid.UUID | None = None
):
    run_id = str(uuid.uuid4())
    tenant_id = get_current_tenant_id()

    # Create run object in the database
    run = Run.objects.create(
        id=run_id,
        tenant_id=tenant_id,
        data={"tool_id": tool_id, "config": config, "input_data": input_data, "db_id": db_id, "toolkit_id": toolkit_id},
        status="started",
        tags=["tool"],
    )

    # Create run context
    context = RunContext(
        run_id=run_id,
        tenant_id=tenant_id,
        tool_id=tool_id,
        tool_config=[{"tool_id": tool_id, "config": config, "name": tool_id, "toolkit_id": toolkit_id}],
    )

    _c = context.model_dump()
    # Add run context
    add_run_context(_c, run_id)

    try:
        yield run, _c
    finally:
        # Update run status
        run.status = "completed"
        run.save()

        # Clear run context
        clear_run_context(run_id)
