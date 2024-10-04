from uuid import uuid4

import pytest

from marvin.beta.local.assistant import LocalAssistant
from marvin.extensions.context.tenant import set_current_tenant_id
from marvin.extensions.executors.thread_run_executor import (
    start_run,
)
from marvin.extensions.types import ChatMessage, MessageRole
from marvin.extensions.types.agent import AgentConfig
from marvin.extensions.types.start_run import TriggerAgentRun
from marvin.extensions.utilities.setup_storage import (
    setup_peewee_sqlite_stores,
)

COMPLEX_TASK = """
Create a chart using the following data:

{
    "data": [
        {"name": "A", "value": 10},
        {"name": "B", "value": 20},
        {"name": "C", "value": 30},
    ]
}

It should be a matplot lib chart.

"""


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


@pytest.mark.asyncio(timeout=120)
async def test_assistant_code_interpreter():
    start_run_payload = create_start_run_payload(str(uuid4()), str(uuid4()))
    set_current_tenant_id(start_run_payload.tenant_id)

    tool_message = ChatMessage(
        role=MessageRole.USER,
        content=[
            {
                "type": "text",
                "text": {
                    "value": COMPLEX_TASK,
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
    default_agent.builtin_toolkits = ["web_browser", "code_interpreter"]
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
        tool_calls[0].code_interpreter
    ), f"Tool call name is not code_interpreter {tool_calls[0].model_dump()}"
    assert (
        tool_calls[0].code_interpreter.input is not None
    ), f"Tool call output is not set {tool_calls[0].code_interpreter.input}"

    outputs = tool_calls[0].code_interpreter.outputs
    assert len(outputs) == 1, f"Expected 1 output, got {len(outputs)} {outputs}"
    assert (
        outputs[0].image.file_id is not None
    ), f"Expected image file_id to be set, got {outputs[0].image}"

    # check messages
    messages = await context_stores.message_store.list_async(
        thread_id=start_run_payload.thread_id
    )
    assert len(messages) == 3, f"Expected 3 messages, got {len(messages)} {messages}"
    message_with_tool_call = next(
        (msg for msg in messages if msg.metadata.tool_calls), None
    )
    assert (
        message_with_tool_call is not None
    ), f"Expected message with tool call, got {messages}"
    assert (
        message_with_tool_call.metadata.tool_calls is not None
    ), f"Expected tool calls to be set, got {message_with_tool_call.metadata.tool_calls}"
    assert (
        len(message_with_tool_call.metadata.tool_calls) == 1
    ), f"Expected 1 tool call, got {len(message_with_tool_call.metadata.tool_calls)} {message_with_tool_call.metadata.tool_calls}"
