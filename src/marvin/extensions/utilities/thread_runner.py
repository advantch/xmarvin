"""
Runners for agents.
Used to
    - create the context for the run.
    - ensures all tools, agents, components are available in context

"""

import asyncio
import os
import traceback
from contextlib import contextmanager

import litellm

import rich
from marvin.extensions.event_handlers.default_assistant_event_handler import (
    DefaultAssistantEventHandler,
)
from marvin.beta.assistants import Assistant
from marvin.beta.local.thread import LocalThread
from marvin.extensions.utilities.configure_preset import configure_internal_sql_agent
from marvin.extensions.storage.base import BaseRunStorage, BaseThreadStore
from marvin.extensions.types.start_run import StartRunSchema
from marvin.extensions.monitoring.logging import logger
from marvin.extensions.utilities.tenant import get_current_tenant_id, set_current_tenant_id
from marvin.extensions.settings import extensions_settings

from marvin import settings as marvin_settings
from marvin.extensions.memory.temp_memory import Memory
from marvin.extensions.storage.simple_chatstore import SimpleThreadStore
from marvin.extensions.types import ChatMessage
from marvin.extensions.types.agent import AgentConfig
from marvin.extensions.utilities.assistants_api import create_thread_message
from marvin.extensions.utilities.context import (
    RunContext,
    add_run_context,
    clear_run_context,
)
from marvin.extensions.utilities.streaming import send_app_event


def update_marvin_settings(api_key: str| None = None):
    if api_key:
        marvin_settings.openai.api_key = api_key    


def update_litellm_settings(api_key: str| None = None):
    if api_key:
        litellm.openai.api_key = api_key
    else:
        litellm.openai.api_key = marvin_settings.openai.api_key


def send_close_event(data, event="close", error=None):
    logger.info(
        f"Sending close event: {event} for run: {data.run_id}:{data.channel_id}:{data.thread_id} ? error: {error}"
    )
    send_app_event(
        str(data.channel_id),
        str(data.thread_id),
        {
            "type": "close",
            "event": event,
            "runId": data.run_id,
            "errorDetail": str(error) if event == "error" else None,
            "error": "Something went wrong, please try again later."
            if event == "error"
            else None,
        },
        message_type="message",
        event=event,
        run_id=data.run_id,
    )


def verify_runtime_config(data: StartRunSchema):
    """
    Fetch db agent if available and id provided.
    - add any additional context
    Call this before constructing system prompt
    """
    if data.preset:
        rich.print(f"preset: {data.preset}")
        if data.preset == "admin":
            data = configure_internal_sql_agent(data)
        elif data.preset == "default":
            data.agent_config = AgentConfig.default_agent()
    else:
        agent_config = extensions_settings.agent_storage_class.get_agent_config(data.agent_id)
        data.agent_config = agent_config

    if data.runtime_config:
        data.agent_config.runtime_config = data.runtime_config

    return data


def save_run_data(run, context):
    storage = context.get("storage", {})
    metadata = storage.get("run_metadata", {})
    _run = metadata.pop("run", {})
    _steps = metadata.pop("steps", [])

    run.data = run.data or {}
    run.data.update(
        {
            "run": _run,
            "steps": _steps,
            "metadata": metadata,
        }
    )
    run.save()


@contextmanager
def run_context(payload: StartRunSchema):
    """
    Run and thread are automatically created and managed within this context.
    
    This context manager handles the creation and management of a Run and Thread
    for an AI assistant interaction. It performs the following tasks:
    
    1. Sets the current tenant ID.
    2. Creates or retrieves a Thread from the database.
    3. Initializes a new Run in the database.
    4. Creates a RunContext with relevant information.
    5. Yields the created Run, Thread, and Context for use in the calling code.
    6. Handles exceptions, logging errors and updating the Run status if needed.
    7. Saves run data and clears the run context upon completion.
    
    Args:
        payload (StartRunSchema): Contains all necessary information to start a run.
    
    Yields:
        tuple: A tuple containing (db_run, thread, context)
            - db_run (Run): The database Run object.
            - thread (Thread): The database Thread object.
            - context (dict): The run context dictionary.
    
    Raises:
        Exception: Any exception that occurs during the run is caught, logged,
                   and the run status is updated to 'failed'.
    """

    tenant_id = payload.tenant_id or get_current_tenant_id()
    set_current_tenant_id(tenant_id)

    if not payload.tenant_id:
        payload.tenant_id = tenant_id


    thread = SimpleThreadStore().get_or_add_thread(
        payload.thread_id,
        tenant_id=tenant_id,
        tags=payload.tags,
        user_id=payload.user_id,
        name=payload.message.content[0].text.value,
    )
    payload.thread_id = str(thread.id)

    db_run = extensions_settings.run_storage_class.init_db_run(
        payload.run_id,
        thread.id,
        tenant_id=tenant_id,
        agent_id=payload.agent_id,
        tags=payload.tags or ["chat", "agent"],
    )
    context = RunContext(
        channel_id=payload.channel_id,
        run_id=str(payload.run_id),
        thread_id=str(thread.id),
        tenant_id=str(tenant_id),
        agent_config=payload.agent_config,
    )

    _c = context.model_dump()
    add_run_context(_c, payload.run_id)

    try:
        yield db_run, thread, _c
    except Exception as e:
        logger.error(f"Error executing agent run pre yield: {e}")
        _c["storage"]["errors"].append(str(e))
        db_run.status = "failed"
        send_close_event(payload, "error", e)
        save_run_data(db_run, _c)

    finally:
        # save any data to cache if not failed
        if db_run.status != "failed":
            db_run.status = "completed"
        db_run.save()
        send_close_event(payload, "close")
        save_run_data(db_run, _c)
        clear_run_context(payload.run_id)


def memory_with_storage(
    thread_id, run_id, tenant_id
):

    storage = extensions_settings.chat_store_class(
        run_id=run_id, thread_id=thread_id, tenant_id=tenant_id
    )

    return Memory(
        storage=storage,
        index=thread_id,
        thread_id=thread_id,
    )


def store_remote_thread_message(data: ChatMessage, assistant_thread_id):
    """
    Add messages to remote thread
    Only for assistant mode
    """

    content = data.get_openai_assistant_messages()
    attachments = data.get_openai_assistant_attachments()
    # append any images to content
    file_attachments = []
    for idx, attachment in enumerate(attachments):
        if attachment.get("type") == "image_file":
            content.append(attachment)
        else:
            file_attachments.append(attachment)
    message = create_thread_message(assistant_thread_id, content, file_attachments)
    return message


def handle_assistant_run(
    data: StartRunSchema, thread: BaseThreadStore, run: BaseRunStorage, context: dict
):
    update_marvin_settings()
    # add message to local db(consider skipping this step until later)
    thread.add_message(data.message)
    remote_thread = thread.remote_thread()
    store_remote_thread_message(data.message, remote_thread.id)
    agent_config = data.agent_config

    # we don't persist assistants
    assistant = Assistant(
        model=agent_config.model,
        instructions=agent_config.get_instructions(),
        tools=agent_config.get_assistant_tools(),
        temperature=agent_config.temperature,
    )

    remote_run = remote_thread.run(
        assistant,
        event_handler_class=DefaultAssistantEventHandler,
        event_handler_kwargs={
            "context": context,
            "openai_run_id": run.id,
            "openai_thread_id": remote_thread.id,
            "openai_assistant_id": assistant.id,
            "memory": memory_with_storage(thread.id, run.id, data.tenant_id),
            "cache": extensions_settings.storage.cache,
        },
        tool_choice="auto",
        tools=agent_config.get_assistant_tools(),
    )
    run.external_id = remote_run.run.id
    run.save()
    send_close_event(data, "close")
    return remote_run


def handle_local_run(
    data: StartRunSchema, thread: BaseThreadStore, run: BaseRunStorage, context: dict
):
    update_litellm_settings()
    # memory to use, use the same memory object for handler and thread
    memory = memory_with_storage(thread.id, run.id, data.tenant_id)
    # the agent to use
    assistant = data.agent_config.as_assistant()
    # add an event handler to save run data and streaming
    handler = DefaultAssistantEventHandler(context=context, cache=extensions_settings.storage.cache, memory=memory)

    local_thread = LocalThread.create(
        id=thread.id,
        tenant_id=data.tenant_id,
        tags=data.tags,
        thread_storage=SimpleThreadStore(),
        memory=memory,
    )
    local_thread.add_message(data.message)

    local_run = local_thread.run(
        assistant=assistant,
        context=context,
        event_handler=handler,
    )
    send_close_event(data, "close")
    return local_run


def start_run(data: StartRunSchema):
    """
    Create a new agent run
    This is usually triggered in a separate thread, therefore you need to set tenant_id
    """
    set_current_tenant_id(data.tenant_id)

    # always call this first
    data = verify_runtime_config(data)

    assert (
        data.agent_config is not None
    ), "Agent config is required: Did you forget to call `verify_runtime_config?`"
    send_app_event(
        data.channel_id, 
        data.thread_id, 
        {
            "type": "start",
            "runId": data.run_id,
        }
    )

    # start a context manager here
    with run_context(data) as (run, thread, context):
        try:
            if data.agent_config.mode == "assistant":
                handle_assistant_run(data, thread, run, context)
            else:
                handle_local_run(data, thread, run, context)

        # capture asyncio error
        except asyncio.CancelledError as e:
            logger.error(f"Error executing agent run cancelled: {e}")
            send_close_event(data, "error", e)

        except Exception as e:
            logger.error(f"Error executing agent run: {e}")
            traceback.print_exc()
            send_close_event(data, "error", e)
