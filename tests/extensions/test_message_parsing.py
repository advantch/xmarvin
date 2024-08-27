import uuid
import pytest
from pydantic import ValidationError
from openai.types.beta.threads.runs.function_tool_call import Function, FunctionToolCall

from marvin.extensions.utilities.context import RunContext
from marvin.extensions.utilities.mappers import run_step_to_tool_call_message
from marvin.extensions.storage.simple_chatstore import SimpleRunStore

from marvin.extensions.types import ChatMessage, TextContentBlock
from marvin.extensions.utilities.message_parsing import (
    format_message_for_completion_endpoint,
)
from marvin.extensions.types.agent import AgentConfig


pytestmark = pytest.mark.django_db


@pytest.fixture
def context(tenant_user):
    tenant_user.set_session_tenant(tenant_id=tenant_user.tenant.id)
    run = SimpleRunStore.objects.init_db_run(
        run_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
    )

    return RunContext(
        channel_id=uuid.uuid4(),
        run_id=run.id,
        thread_id=run.thread_id,
        tenant_id=tenant_user.tenant.id,
        agent_config=AgentConfig.default_agent(),
        tool_config=[],
    )


def test_chat_message_parsing():
    # Sample message to be parsed
    # create a dataset with some files
    message = """{
        "id": "b73fd271-fa14-468f-95ae-25c2cd1db824",
        "role": "user",
        "run_id": null,
        "content": [
            {
                "text": {
                    "value": "describe the image",
                    "annotations": []
                },
                "type": "text"
            }
        ],
        "metadata": {
            "id": "",
            "name": null,
            "type": "message",
            "run_id": "",
            "streaming": false,
            "raw_output": null,
            "tool_calls": null,
            "attachments": [
                {
                    "type": "image",
                    "file_id": "file-123",
                    "metadata": {
                        "url": "/media/dicts/pic.png"
                    }
                }
            ]
        },
        "thread_id": null
    }"""

    try:
        message = ChatMessage.model_validate_json(message)
    except ValidationError as exc:
        print(repr(exc.errors()[0]["type"]))
    assert message.metadata.attachments[0].type == "image"
    assert message.metadata.attachments[0].metadata.url == "/media/dicts/pic.png"


def test_runner_message_parsing(
    run_step_factory, tool_calls_step_details_factory, context
):
    # create a run step with tool calls
    run_step = run_step_factory.build()
    run_step.type = "tool_calls"
    run_step.step_details = tool_calls_step_details_factory.build()
    # explicitly add function tool calls here
    tool_calls = FunctionToolCall(
        id=str(uuid.uuid4()),
        function=Function(
            name="google search", arguments="cars and cats", output="1: cars 2: cats"
        ),
        type="function",
    )
    run_step.step_details.tool_calls = [tool_calls]

    tool_call_count = len(run_step.step_details.tool_calls)
    message = run_step_to_tool_call_message(run_step, context)
    message.content = [
        TextContentBlock.model_validate(
            {"text": {"value": "describe the image", "annotations": []}, "type": "text"}
        )
    ]
    assert isinstance(message, ChatMessage)
    assert message.content[0].type == "text"
    assert message.content[0].text.value == "describe the image"

    formatted_message = format_message_for_completion_endpoint([message])
    assert len(formatted_message) == tool_call_count + 1
