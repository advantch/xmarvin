import traceback
from uuid import uuid4

from marvin.extensions.utilities.logging import pretty_log

import pytest
from marvin.beta.local.assistant import LocalAssistant
from marvin.beta.local.handlers import DefaultAssistantEventHandler
from marvin.beta.local.run import LocalRun, RunStatus
from marvin.beta.local.thread import LocalThread
from marvin.extensions.memory.temp_memory import Memory
from marvin.extensions.storage.cache import SimpleCache
from marvin.extensions.storage.memory_store import MemoryChatStore
from marvin.extensions.types import ChatMessage, MessageRole
from marvin.extensions.types.agent import AgentConfig
from marvin.extensions.types.start_run import TriggerAgentRun
from marvin.extensions.utilities.context import RunContext
from marvin.extensions.utilities.tenant import set_current_tenant_id
from marvin.extensions.utilities.thread_runner import (
    handle_assistant_run,
    handle_local_run,
    run_context,
    verify_runtime_config,
)


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
                    "text": {"value": "Search for top AI tools", "annotations": []},
                }
            ],
            metadata={"attachments": [], "run_id": run_id},
        ),
        tenant_id=str(uuid4()),
    )

@pytest.fixture
def start_run_payload_with_tools():
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
                    "text": {"value": "Fetch the example.com website", "annotations": []},
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
        tools=[],
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
    messages = [{"role": "user", "content": "Search for top AI tools"}]
    return await acompletion(
        model=model,
        messages=messages,
        stream=True,
        mock_response="Here are some top AI tools: 1. TensorFlow, 2. PyTorch, 3. Scikit-learn, 4. OpenAI GPT, 5. Google Cloud AI Platform",
    )


@pytest.mark.asyncio
async def test_run_with_tools(start_run_payload, local_assistant, mocker):
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
    cache = SimpleCache()
    storage = MemoryChatStore()
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
    assert "top AI tools" in messages[1].content[0].text.value


@pytest.mark.asyncio
async def test_remote_agent(start_run_payload_with_tools, mocker):
    set_current_tenant_id(start_run_payload_with_tools.tenant_id)

    default_agent = AgentConfig.default_agent()
    default_agent.mode = "assistant"
    default_agent.builtin_toolkits = ["web_browser"]
    start_run_payload_with_tools.agent_config = default_agent
    data = verify_runtime_config(start_run_payload_with_tools)

    # Check tools
    assert data.agent_config.get_assistant_tools()[0].function.name == "web_browser"
    assert len(data.agent_config.builtin_toolkits) == 1

    assert (
        data.agent_config is not None
    ), "Agent config is required: Did you forget to call `verify_runtime_config?`"

    with run_context(data) as (run_storage, thread, context):
        try:
            if data.agent_config.mode == "assistant":
                handle_assistant_run(data, thread, run_storage, context)
            else:
                handle_local_run(data, thread, run_storage, context)
        except Exception as e:
            traceback.print_exc()
            raise e

    run = run_storage.get(data.run_id)
    assert run.status == RunStatus.COMPLETED

    assert len(run.steps) == 2

    # details = run.steps[0].step_details
    # assert getattr(details, "tool_calls", None) is not None
    # tool_calls = run.steps[0].step_details.tool_calls
    # assert len(tool_calls) == 1

    # messages = await thread.list_messages_async(index=data.thread_id)
    # assert len(messages) == 4, len(messages)
    # # Check the second message is a tool call
    # m = messages[1]
    # assert m.role == MessageRole.ASSISTANT
    # assert len(m.metadata.tool_calls) == 1
    # assert m.metadata.tool_calls[0].type == "web_browser"
