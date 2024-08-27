import uuid
import pytest
from unittest.mock import AsyncMock, patch
from marvin.beta.local.handlers import DefaultAssistantEventHandler
from marvin.extensions.utilities.context import RunContext
from marvin.extensions.storage.simple_chatstore import SimpleRunStore, SimpleChatStore
from marvin.extensions.types.agent import AgentConfig
from marvin.extensions.memory.temp_memory import Memory
from ..factories import (
    MessageFactory,
    MessageDeltaFactory,
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
    run_store = SimpleRunStore()
    chat_store = SimpleChatStore()
    
    run = run_store.init_db_run(
        run_id=str(uuid.uuid4()),
        thread_id=str(uuid.uuid4()),
    )
    context = RunContext(
        channel_id=str(uuid.uuid4()),
        run_id=run.id,
        thread_id=run.thread_id,
        tenant_id=str(uuid.uuid4()),
        agent_config=AgentConfig.default_agent(),
        tool_config=[],
    )
    _context = context.model_dump()
    memory = Memory(storage=chat_store, context=_context, thread_id=run.thread_id, index=run.thread_id)

    handler = DefaultAssistantEventHandler(context=_context, memory=memory)

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
    messages = await memory.storage.get_messages_async(run.thread_id)
    assert messages is not None
    #assert len(messages) == 1, messages
    
    assert await memory.storage.get_messages_async(run.thread_id) is not None

    # check there is a storage object
    assert handler._context['storage'] is not None
    assert handler._context['storage']['tool_calls'] is not None

