import asyncio
import uuid

import pytest
from httpx import Response

from marvin.extensions.context.run_context import (
    RunContext,
    get_current_run,
    get_current_run_id,
    get_run_context,
)
from marvin.extensions.executors.thread_run_executor import initialise_run
from marvin.extensions.types import ChatMessage, Metadata
from marvin.extensions.types.agent import AgentConfig
from marvin.extensions.types.start_run import TriggerAgentRun
from marvin.extensions.utilities.setup_storage import setup_memory_stores


@pytest.mark.no_llm
def test_thread_runner(respx_mock):
    tenant_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    channel_id = str(uuid.uuid4())
    thread_id = str(uuid.uuid4())
    respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"content": "Hello, world!"}}]},
        )
    )

    message = ChatMessage(
        id=str(uuid.uuid4()),
        role="user",
        run_id=None,
        content=[
            {"text": {"value": "hello", "annotations": []}, "type": "text"},
        ],
        metadata=Metadata(
            id="",
            name=None,
            type="message",
            run_id="",
            streaming=False,
            raw_output=None,
            tool_calls=None,
        ),
        thread_id=thread_id,
    )
    data = TriggerAgentRun(
        message=message,
        run_id=run_id,
        thread_id=thread_id,
        channel_id=channel_id,
        tenant_id=tenant_id,
        run_type="chat",
        messages=[message],
        agent_config=AgentConfig.default_agent(),
    )

    async def launch_async_task():
        await asyncio.sleep(1)
        run_context = RunContext(**get_run_context(get_current_run_id()))
        assert str(run_context.run_id) == str(data.run_id)
        assert str(run_context.thread_id) == str(data.thread_id)

    context_stores = setup_memory_stores()
    initialise_run(data, context_stores.run_store)

    with RunContext(
        channel_id=data.channel_id,
        run_id=data.run_id,
        thread_id=data.thread_id,
        tenant_id=data.tenant_id,
        agent_config=data.agent_config,
        stores=context_stores,
    ) as run_ctx:
        assert str(run_ctx.run_id) == str(data.run_id)

        # try get tenant_id
        current_run_id = get_current_run_id()
        assert str(current_run_id) == str(data.run_id)
        in_run_context = get_current_run()
        assert str(in_run_context.tenant_id) == str(tenant_id)
        assert str(in_run_context.channel_id) == str(channel_id)

        asyncio.run(launch_async_task())

        assert get_current_run() is not None

    # outside context
    run = get_current_run()
    assert run is None

    current_run_id = get_current_run_id()
    assert current_run_id is None
