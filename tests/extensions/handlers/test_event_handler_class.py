import uuid

import pytest

from marvin.beta.local.handlers import DefaultAssistantEventHandler
from marvin.extensions.context.run_context import RunContext
from marvin.extensions.types.agent import AgentConfig
from marvin.extensions.utilities.setup_storage import setup_memory_stores

from ..factories import (
    MessageDeltaFactory,
    MessageFactory,
    RunFactory,
    RunStepDeltaFactory,
    RunStepFactory,
    ThreadRunCompletedFactory,
    ThreadRunFailedFactory,
    ToolCallDeltaObjectFactory,
    ToolCallsStepDetailsFactory,
)


@pytest.mark.asyncio
async def test_event_handler_class():
    stores = setup_memory_stores()
    run_id = str(uuid.uuid4())
    run = stores.run_store.init_db_run(
        run_id=run_id,
        thread_id=str(uuid.uuid4()),
    )
    with RunContext(
        channel_id=str(uuid.uuid4()),
        run_id=run_id,
        thread_id=run.thread_id,
        tenant_id=str(uuid.uuid4()),
        agent_config=AgentConfig.default_agent(),
        tool_config=[],
        stores=stores,
    ) as context:
        _context = context.model_dump()

        handler = DefaultAssistantEventHandler(
            context=context, memory=context.runtime_memory
        )

        # Test on_message_delta
        delta = MessageDeltaFactory.build()
        snapshot = MessageFactory.build()
        await handler.on_message_delta(delta, snapshot)

        # Test on_message_done
        message = MessageFactory.build()
        await handler.on_message_done(message)

        # Test on_run_step_delta
        step_delta = RunStepDeltaFactory.build()
        step_snapshot = RunStepFactory.build()
        step_snapshot.type = "tool_calls"
        step_snapshot.step_details = ToolCallDeltaObjectFactory.build()
        await handler.on_run_step_delta(step_delta, step_snapshot)

        # Test on_run_step_done
        run_step = RunStepFactory.build()
        run_step.type = "tool_calls"
        run_step.step_details = ToolCallsStepDetailsFactory.build()
        await handler.on_run_step_done(run_step)

        # Test on_exception
        exc = Exception("Test exception")
        await handler.on_exception(exc)

        # Test on_event (run completed)
        run = RunFactory.build()
        run.model = "gpt-4"
        event_completed = ThreadRunCompletedFactory.build(data=run)
        await handler.on_event(event_completed)

        # Test on_event (run failed)
        run_failed = RunFactory.build(status="failed")
        event_failed = ThreadRunFailedFactory.build(data=run_failed)
        await handler.on_event(event_failed)

        # Add assertions here to verify the expected behavior
        # For example:
        messages = await stores.message_store.list_async(thread_id=run.thread_id)
        assert messages is not None
        # assert len(messages) == 1, messages

        assert (
            await stores.message_store.list_async(thread_id=run.thread_id) is not None
        )
