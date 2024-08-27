import pytest
import asyncio
from marvin.extensions.utilities.context import (
    RunContext,
    get_current_run_id,
    get_run_context,
)
from marvin.extensions.utilities.thread_runner import run_context
from marvin.extensions.types.start_run import TriggerAgentRun
import uuid

from httpx import Response
from marvin.extensions.types import Metadata, ChatMessage
from marvin.extensions.types.agent import AgentConfig


pytestmark = pytest.mark.django_db


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
    start_run_schema = TriggerAgentRun(
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
        assert str(run_context.run_id) == str(start_run_schema.run_id)
        assert str(run_context.thread_id) == str(start_run_schema.thread_id)


    with run_context(start_run_schema) as (run, thread_storage, context):
        assert str(run.id) == str(start_run_schema.run_id)
        
        # try get tenant_id
        current_run_id = get_current_run_id()
        assert str(current_run_id) == str(start_run_schema.run_id)
        in_run_context = RunContext(**get_run_context(current_run_id))
        assert str(in_run_context.tenant_id) == str(tenant_id)
        assert str(in_run_context.channel_id) == str(channel_id)

        asyncio.run(launch_async_task())

    # outside context
    current_run_id = get_current_run_id()
    assert current_run_id is None
