import json
from uuid import uuid4

import pytest

from marvin.beta.local.assistant import LocalAssistant
from marvin.extensions.context.tenant import set_current_tenant_id
from marvin.extensions.executors.thread_run_executor import (
    handle_assistant_run,
    handle_local_run,
    start_run,
)
from marvin.extensions.types import ChatMessage, MessageRole
from marvin.extensions.types.agent import AgentConfig, RuntimeConfig
from marvin.extensions.types.llms import AIModels
from marvin.extensions.types.start_run import TriggerAgentRun
from marvin.extensions.utilities.setup_storage import (
    setup_peewee_sqlite_stores,
)


def create_start_run_payload(run_id, thread_id):
    return TriggerAgentRun(
        run_id=run_id,
        channel_id=str(uuid4()),
        thread_id=thread_id,
        message=ChatMessage(
            role=MessageRole.USER,
            content=[
                {
                    "type": "text",
                    "text": {"value": "Hello, world!", "annotations": []},
                }
            ],
            metadata={"attachments": [], "run_id": run_id},
            thread_id=thread_id,
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
async def test_local_run():
    start_run_payload = create_start_run_payload(str(uuid4()), str(uuid4()))
    set_current_tenant_id(start_run_payload.tenant_id)

    # Setup memory stores
    # context_stores = setup_memory_stores()
    context_stores = setup_peewee_sqlite_stores()

    # Update the start_run_payload with the local_assistant as the agent_config
    start_run_payload.agent_config = AgentConfig.default_agent()
    start_run_payload.agent_config.mode = "agent"
    # Handle the local run
    local_run = await handle_local_run(start_run_payload, context_stores)

    # Assertions
    assert str(local_run.id) == str(start_run_payload.run_id)
    assert str(local_run.thread.id) == str(start_run_payload.thread_id)

    stored_run = await context_stores.run_store.get_run_async(start_run_payload.run_id)
    assert stored_run is not None, f"Run is not stored {stored_run}"
    assert (
        stored_run.status == "completed"
    ), f"Run status is not completed {stored_run.status}"
    assert (
        len(stored_run.metadata.get("credits")) > 0
    ), f"Run metadata credits is not set {stored_run.metadata}"

    # Get messages from the thread
    thread = local_run.thread
    messages = await thread.list_messages_async()

    assert len(messages) == 2  # User message and assistant's response
    assert messages[0].role == MessageRole.USER
    assert messages[1].role == MessageRole.ASSISTANT


@pytest.mark.no_llm
@pytest.mark.asyncio
async def test_assistant_run():
    start_run_payload = create_start_run_payload(str(uuid4()), str(uuid4()))
    set_current_tenant_id(start_run_payload.tenant_id)

    # Setup memory stores
    # context_stores = setup_memory_stores()
    context_stores = setup_peewee_sqlite_stores()

    # Update the start_run_payload for assistant run
    start_run_payload.agent_config = AgentConfig.default_agent()
    start_run_payload.agent_config.mode = "assistant"

    # Handle the assistant run
    await handle_assistant_run(start_run_payload, context_stores)

    # Check if the thread was created and messages were added
    thread = await context_stores.thread_store.get_thread_async(
        start_run_payload.thread_id, tenant_id=start_run_payload.tenant_id
    )
    assert thread is not None
    assert str(thread.id) == str(start_run_payload.thread_id)
    assert (
        thread.external_id is not None
    ), f"Thread external ID is not set {start_run_payload.thread_id} {start_run_payload.tenant_id}"

    # Verify that the run was stored
    stored_run = await context_stores.run_store.get_run_async(start_run_payload.run_id)
    assert stored_run is not None, f"Run is not stored {stored_run}"
    assert (
        stored_run.status == "completed"
    ), f"Run status is not completed {stored_run.status}"
    assert (
        len(stored_run.metadata.get("credits")) > 0
    ), f"Run metadata credits is not set {stored_run.metadata}"


@pytest.mark.asyncio
async def test_assistant_run_with_tools():
    start_run_payload = create_start_run_payload(str(uuid4()), str(uuid4()))
    set_current_tenant_id(start_run_payload.tenant_id)

    tool_message = ChatMessage(
        role=MessageRole.USER,
        content=[
            {
                "type": "text",
                "text": {
                    "value": "Fetch example.com and summarize the results",
                    "annotations": [],
                },
            }
        ],
        metadata={"attachments": [], "run_id": start_run_payload.run_id},
        thread_id=start_run_payload.thread_id,
    )
    start_run_payload.message = tool_message

    context_stores = setup_peewee_sqlite_stores()
    default_agent = AgentConfig.default_agent()
    default_agent.mode = "assistant"
    default_agent.builtin_toolkits = ["web_browser"]
    start_run_payload.agent_config = default_agent
    start_run_payload.agent_config.mode = "assistant"

    await start_run(start_run_payload, context_stores)

    stored_run = await context_stores.run_store.get_run_async(start_run_payload.run_id)
    assert stored_run is not None, f"Run is not stored {stored_run}"
    assert (
        stored_run.status == "completed"
    ), f"Run status is not completed {stored_run.status}"
    assert (
        len(stored_run.metadata.get("credits")) > 0
    ), f"Run metadata credits is not set {stored_run.metadata}"

    steps = stored_run.steps
    assert (
        len(steps) == 2
    ), f"Expected 2 steps, a tool call and message creation. got {len(steps)}"
    assert (
        steps[0].status == "completed"
    ), f"Step status is not completed {steps[0].status}"

    # test tool call are valid
    tool_calls = steps[0].step_details.tool_calls
    assert len(tool_calls) == 1, f"Expected 1 tool call, got {len(tool_calls)}"
    assert (
        tool_calls[0].function.name == "web_browser"
    ), f"Tool call name is not web_browser {tool_calls[0].model_dump()}"
    assert (
        tool_calls[0].function.arguments is not None
    ), f"Tool call output is not set {tool_calls[0].function.arguments}"
    assert (
        "example.com" in json.loads(tool_calls[0].function.arguments)["url"]
    ), f"Tool call arguments are not set {tool_calls[0].function.arguments}"


# do the same for local run


@pytest.mark.asyncio
async def test_local_run_with_tools():
    start_run_payload = create_start_run_payload(str(uuid4()), str(uuid4()))
    set_current_tenant_id(start_run_payload.tenant_id)

    tool_message = ChatMessage(
        role=MessageRole.USER,
        content=[
            {
                "type": "text",
                "text": {
                    "value": "Fetch example.com and summarize the results",
                    "annotations": [],
                },
            }
        ],
        metadata={"attachments": [], "run_id": start_run_payload.run_id},
        thread_id=start_run_payload.thread_id,
    )
    start_run_payload.message = tool_message

    context_stores = setup_peewee_sqlite_stores()
    default_agent = AgentConfig.default_agent()
    default_agent.mode = "agent"
    default_agent.builtin_toolkits = ["web_browser"]
    start_run_payload.agent_config = default_agent
    start_run_payload.agent_config.mode = "agent"
    runtime_config = RuntimeConfig(model=AIModels.CLAUDE_3_5_SONNET)
    start_run_payload.runtime_config = runtime_config

    await start_run(start_run_payload, context_stores)

    stored_run = await context_stores.run_store.get_run_async(start_run_payload.run_id)
    assert stored_run is not None, f"Run is not stored {stored_run}"
    assert (
        stored_run.status == "completed"
    ), f"Run status is not completed {stored_run.status}"
    assert (
        len(stored_run.metadata.get("credits")) > 0
    ), f"Run metadata credits is not set {stored_run.metadata}"

    steps = stored_run.steps
    assert (
        len(steps) == 2
    ), f"Expected 2 steps, a tool call and message creation. got {len(steps)}"
    assert (
        steps[0].status == "completed"
    ), f"Step status is not completed {steps[0].status}"

    # test tool call are valid
    tool_calls = steps[0].step_details.tool_calls
    assert len(tool_calls) == 1, f"Expected 1 tool call, got {len(tool_calls)}"
    assert (
        tool_calls[0].function.name == "web_browser"
    ), f"Tool call name is not web_browser {tool_calls[0].function.name}"
    assert (
        tool_calls[0].function.arguments is not None
    ), f"Tool call output is not set {tool_calls[0].function.arguments}"
    assert (
        "example.com" in json.loads(tool_calls[0].function.arguments)["url"]
    ), f"Tool call arguments are not set {tool_calls[0].function.arguments}"
