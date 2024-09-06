from uuid import uuid4

import pytest

from marvin.beta.local.assistant import LocalAssistant
from marvin.beta.local.handlers import DefaultAssistantEventHandler
from marvin.beta.local.run import LocalRun
from marvin.beta.local.thread import LocalThread
from marvin.extensions.context.run_context import RunContext
from marvin.extensions.context.tenant import set_current_tenant_id
from marvin.extensions.memory.temp_memory import Memory
from marvin.extensions.storage.stores import ChatStore
from marvin.extensions.types import ChatMessage, MessageRole
from marvin.extensions.types.start_run import TriggerAgentRun


@pytest.fixture
def start_run_payload():
    run_id = str(uuid4())
    return TriggerAgentRun(
        run_id=run_id,
        channel_id=str(uuid4()),
        thread_id=str(uuid4()),
        message=ChatMessage(
            role=MessageRole.USER,
            content=[
                {
                    "type": "text",
                    "text": {"value": "Hello, world!", "annotations": []},
                }
            ],
            metadata={"attachments": [], "run_id": run_id},
        ),
        tenant_id=str(uuid4()),
    )


@pytest.fixture
def local_assistant():
    return LocalAssistant(
        id="test_assistant_id",
        name="Test Assistant",
        model="gpt-4o-mini",
        instructions="You are a helpful assistant.",
    )


class Cache:
    def __init__(self):
        self.c = {}

    def get(self, key):
        return self.c.get(key)

    def set(self, key, value):
        self.c[key] = value

    def delete(self, key):
        del self.c[key]


async def mocked_get_llm_response(*args, **kwargs):
    from litellm import acompletion

    model = "gpt-3.5-turbo"
    messages = [{"role": "user", "content": "Hey, I'm a mock request"}]
    return await acompletion(
        model=model,
        messages=messages,
        stream=True,
        mock_response="It's simple to use and easy to get started",
    )


@pytest.mark.no_llm
@pytest.mark.asyncio
async def test_local_run(start_run_payload, local_assistant, mocker):
    set_current_tenant_id(start_run_payload.tenant_id)

    mocker.patch.object(
        LocalRun, "_get_llm_response", side_effect=mocked_get_llm_response
    )
    context = RunContext(
        run_id=start_run_payload.run_id,
        thread_id=start_run_payload.thread_id,
        tenant_id=start_run_payload.tenant_id,
    )
    c = context.model_dump()
    cache = Cache()
    storage = ChatStore()
    memory = Memory(
        storage=storage,
        context=c,
        thread_id=start_run_payload.thread_id,
        index=start_run_payload.thread_id,
    )

    handler = DefaultAssistantEventHandler(context=c, cache=cache, memory=memory)
    thread = await LocalThread.create_async(
        id=start_run_payload.thread_id, memory=memory
    )
    run = LocalRun(
        id=start_run_payload.run_id,
        assistant=local_assistant,
        thread=thread,
        handler=handler,
    )

    await run.execute_async(message=start_run_payload.message)
    run = run.run
    assert run.id == str(start_run_payload.run_id)
    assert run.thread_id == str(start_run_payload.thread_id)
    assert run.assistant_id == str(local_assistant.id)
    assert run.status == "completed"

    messages = await thread.list_messages_async(index=start_run_payload.thread_id)
    assert len(messages) == 2  # User message and assistant's response
    assert messages[0].role == MessageRole.USER
    assert messages[1].role == MessageRole.ASSISTANT
