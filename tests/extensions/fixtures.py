import pytest
from datetime import datetime, timedelta
from polyfactory.pytest_plugin import register_fixture
from .factories import (
    ChatCompletionChunkFactory,
    MessageFactory,
    MessageDeltaFactory,
    RunStepFactory,
    RunStepDeltaFactory,
    RunFactory,
    ThreadRunCompletedFactory,
    ThreadRunFailedFactory,
    ToolCallDeltaObjectFactory,
    ToolCallsStepDetailsFactory,
)
import uuid
from marvin.extensions.types.agent import AgentConfig


@pytest.fixture
def completion_chunk_generator():
    m = [ChatCompletionChunkFactory.build() for _ in range(3)]
    for chunk in m:
        yield chunk


@pytest.fixture
def completion_chunks():
    m = [ChatCompletionChunkFactory.build() for _ in range(3)]
    return m


docs_instructions = """
    You are an expert in technical writing. You strive 
    to condense complex subjects into clear, concise language.
    Your goal is to provide the user with accurate, informative 
    documentation that is easy to understand. Follow the Diátaxis framework.
"""

editor_instructions = """
    You are an expert in technical writing. You strive 
    to condense complex subjects into clear, concise language.
    Your goal is to provide the user with accurate, informative 
    documentation that is easy to understand. Follow the Diátaxis framework.
"""
task_instructions = """
    "Write a technical document that explains agentic workflows."
    "The docs agent should generate the document, "
    "after which the editor agent should review and "
    "edit it. Only the editor can mark the task as complete."
"""
flow_config = {
    "agent_templates": [
        {
            "name": "DocsBot",
            "description": "An agent that specializes in writing technical documentation",
            "instructions": docs_instructions,
        },
        {
            "name": "EditorBot",
            "description": "An agent that specializes in editing technical documentation",
            "instructions": editor_instructions,
        },
    ],
    "task_templates": [
        {
            "id": 1,
            "objective": "Write a technical document",
            "agents": ["DocsBot", "EditorBot"],
            "result_type": str,
            "instructions": task_instructions,
        },
        {
            "id": 2,
            "objective": "Persist the document to a file",
            "result_type": str,
            "instructions": " Save the document to a file.",
            "tools": ["save_to_file"],
        },
    ],
}


# Example usage
docs_agent_config = AgentConfig(
    id=str(uuid.uuid4()),
    name="DocsBot",
    description="Documentation writer",
    instructions={"text": docs_instructions},
)
editor_agent_config = AgentConfig(
    id=str(uuid.uuid4()),
    name="EditorBot",
    description="Editor",
    instructions={"text": editor_instructions},
)

node_id_0 = str(0)
node_id_1 = str(1)
node_id_2 = str(2)
node_id_3 = str(uuid.uuid4())
node_id_4 = str(uuid.uuid4())
react_flow_json = {
    "nodes": [
        {
            "id": node_id_0,
            "type": "trigger",
            "data": {
                "id": "0",
                "type": "trigger",
                "name": "Trigger",
                "description": "Trigger",
                "schedule": "run_once",
            },
        },
        {
            "id": node_id_1,
            "type": "task",
            "data": {
                "id": "1",
                "type": "task",
                "name": "Write Technical Document",
                "objective": "Write a technical document",
                "result_type": "str",
                "instructions": task_instructions,
                "agents": [docs_agent_config.id, editor_agent_config.id],
            },
        },
        {
            "id": node_id_2,
            "type": "task",
            "data": {
                "id": "2",
                "type": "task",
                "name": "Database",
                "objective": "Save file to local directory as markdown `document.md`",
                "description": "Database",
                "instructions": "Save file to local directory as markdown `document.md`",
                "tools": ["save_to_file"],
            },
        },
    ],
    "edges": [
        {
            "id": "e1-1",
            "source": str(node_id_1),
            "target": str(node_id_2),
            "sourceHandle": "task",
            "targetHandle": "task",
        },
        {
            "id": "e1-0",
            "source": str(node_id_0),
            "target": str(node_id_1),
            "sourceHandle": "trigger",
            "targetHandle": "trigger",
        },
    ],
}


@pytest.fixture
def react_flow_data():
    return react_flow_json

@pytest.fixture
def rflow_future_scheduled(react_flow_data):
    react_flow_data["nodes"][0]["data"]["schedule"] = "specific_time"
    react_flow_data["nodes"][0]["data"]["scheduled_at"] = (datetime.now() + timedelta(days=1)).isoformat()
    return react_flow_data


@pytest.fixture
def agent_configs():
    return [docs_agent_config, editor_agent_config]


@pytest.fixture
def node_config_ids():
    return {
        "node_id_0": node_id_0,
        "node_id_1": node_id_1,
        "node_id_2": node_id_2,
        "node_id_3": node_id_3,
        "node_id_4": node_id_4,
    }


@pytest.fixture
def task_instructions_example():
    return task_instructions


message_delta_factory = register_fixture(MessageDeltaFactory)
message_factory = register_fixture(MessageFactory)
run_step_factory = register_fixture(RunStepFactory)
run_step_delta_factory = register_fixture(RunStepDeltaFactory)
run_factory = register_fixture(RunFactory)
thread_run_completed_factory = register_fixture(ThreadRunCompletedFactory)
thread_run_failed_factory = register_fixture(ThreadRunFailedFactory)
tool_call_delta_object_factory = register_fixture(ToolCallDeltaObjectFactory)
tool_calls_step_details_factory = register_fixture(ToolCallsStepDetailsFactory)
