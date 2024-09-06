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

from marvin import settings as marvin_settings
from marvin.beta.assistants import Assistant
from marvin.beta.assistants.threads import Thread
from marvin.beta.local.handlers import (
    DefaultAssistantEventHandler,
)
from marvin.beta.local.thread import LocalThread
from marvin.extensions.context.run_context import (
    RunContext,
    add_run_context,
    clear_run_context,
)
from marvin.extensions.context.tenant import (
    get_current_tenant_id,
    set_current_tenant_id,
)
from marvin.extensions.memory.temp_memory import Memory
from marvin.extensions.settings import extension_settings
from marvin.extensions.storage.base import (
    BaseAgentStorage,
    BaseChatStore,
    BaseRunStorage,
    BaseThreadStore,
)
from marvin.extensions.storage.stores import (
    ChatStore,
    RunStore,
    ThreadStore,
)
from marvin.extensions.types import ChatMessage
from marvin.extensions.types.agent import AgentConfig
from marvin.extensions.types.start_run import TriggerAgentRun
from marvin.extensions.utilities.assistants_api import create_thread_message
from marvin.extensions.utilities.configure_preset import configure_internal_sql_agent
from marvin.extensions.utilities.logging import logger, pretty_log
from marvin.extensions.utilities.message_parsing import (
    get_openai_assistant_attachments,
    get_openai_assistant_messages,
)
from marvin.extensions.utilities.streaming import send_app_event


def update_marvin_settings(api_key: str | None = None):
    if api_key:
        marvin_settings.openai.api_key = api_key
    else:
        marvin_settings.openai.api_key = os.getenv("OPENAI_API_KEY")


def update_litellm_settings(api_key: str | None = None):
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


def verify_runtime_config(
    data: TriggerAgentRun,
    agent_storage: BaseAgentStorage | None = None,
):
    """
    Validate and configure runtime config for agent.
    Fetch db agent if available and id provided.
    - add any additional context
    - fetch and add tools and related configs.
    Existing config will not be overwritten.

    # TODO: support for fetchin remote agents?
    # TODO: verify agent belongs to tenant

    NB: Call this before creating context for run.
    """
    default_config = AgentConfig.default_agent()
    if data.preset:
        rich.print(f"preset: {data.preset}")
        if data.preset == "admin":
            data.agent_config = configure_internal_sql_agent(data)
        elif data.preset == "default":
            data.agent_config = default_config

    # this assumes you are storing the agents in some storage,
    # existing config will not be overwritten
    if data.agent_id and data.agent_config is None:
        rich.print(f"agent_id: {data.agent_id}")
        agent_storage = (
            agent_storage or extension_settings.storage.agent_storage_class()
        )
        agent_config = agent_storage.get_agent_config(data.agent_id)
        data.agent_config = agent_config or default_config

    if data.runtime_config:
        data.agent_config.runtime_config = data.runtime_config

    return data


@contextmanager
def run_context(
    payload: TriggerAgentRun,
    thread_storage_class: type[BaseThreadStore] | None = ThreadStore,
    thread_store: BaseThreadStore | None = None,
    run_storage_class: type[BaseRunStorage] | None = RunStore,
):
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
        payload (TriggerAgentRun): Contains all necessary information to start a run.

    Yields:
        tuple: A tuple containing (persisted_run, thread, context)
            - persisted_run (PersistedRun): The database/storage Run object.
            - thread (ChatThread): The database/storage ChatThread object.
            - context (dict): The run context dictionary.

    Raises:
        Exception: Any exception that occurs during the run is caught, logged,
                   and the run status is updated to 'failed'.
    """

    tenant_id = payload.tenant_id or get_current_tenant_id()
    set_current_tenant_id(tenant_id)

    if not payload.tenant_id:
        payload.tenant_id = tenant_id

    thread_store = thread_store or thread_storage_class()
    thread = thread_store.get_or_add_thread(
        payload.thread_id,
        tenant_id=tenant_id,
        tags=payload.tags,
        user_id=payload.user_id,
        name=payload.message.content[0].text.value,
    )

    run_storage_class = (
        run_storage_class or extension_settings.storage.run_storage_class
    )
    run_storage = run_storage_class()
    persisted_run = run_storage.init_db_run(
        payload.run_id,
        thread.id,
        tenant_id=tenant_id,
        agent_id=payload.agent_id,
        tags=payload.tags or ["chat", "agent"],
    )
    context = RunContext(
        channel_id=payload.channel_id,
        run_id=str(payload.run_id),
        thread_id=str(payload.thread_id),
        tenant_id=str(tenant_id),
        agent_config=payload.agent_config,
    )

    context_object = context.model_dump()
    add_run_context(context_object, payload.run_id)

    try:
        yield run_storage, thread_store, context_object
    except Exception as e:
        logger.error(f"Error executing agent run pre yield: {e}")
        context_object["storage"]["errors"].append(str(e))
        persisted_run.status = "failed"
        send_close_event(payload, "error", e)

    finally:
        # save any data to cache if not failed
        if persisted_run.status != "failed":
            persisted_run.status = "completed"

        send_close_event(payload, "close")
        pretty_log(context_object, persisted_run.model_dump())
        persisted_run.save_run_context_data(context_object)

        run_storage.update(persisted_run)
        clear_run_context(payload.run_id)


def memory_with_storage(thread_id, storage=None):
    return Memory(
        storage=storage or {},
        index=thread_id,
        thread_id=thread_id,
    )


def create_openai_thread(thread_id):
    from marvin.beta.assistants import Thread

    thread = Thread()
    thread = thread.create()
    return thread


def add_message_to_remote_thread(data: ChatMessage, assistant_thread_id):
    """
    Add messages to remote thread

    Only necessary for attachments and images. To remove when that is handled properly.
    """

    content = get_openai_assistant_messages(data)
    attachments = get_openai_assistant_attachments(data)
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
    data: TriggerAgentRun,
    thread_store: BaseThreadStore,
    run_storage: BaseRunStorage,
    context: dict,
    chat_store: BaseChatStore | None = None,
    chat_storage_class: type[BaseChatStore] | None = ChatStore,
):
    update_marvin_settings()
    tenant_id = data.tenant_id or get_current_tenant_id()

    # initialise any storage
    storage = chat_store or chat_storage_class()
    memory = memory_with_storage(data.thread_id, storage)
    thread = thread_store.get_or_add_thread(data.thread_id, tenant_id=tenant_id)

    # fetch the remote thread
    if thread.external_id:
        remote_thread = Thread(thread.external_id)
    else:
        remote_thread = create_openai_thread(data.thread_id)
        thread.external_id = remote_thread.id
        thread_store.update(thread)

    add_message_to_remote_thread(data.message, remote_thread.id)
    agent_config = data.agent_config

    # we don't persist assistants for now
    assistant = Assistant(
        model=agent_config.model,
        instructions=agent_config.get_instructions(),
        tools=agent_config.get_assistant_tools(),
        temperature=agent_config.temperature,
    )

    # add any initial messages to memory
    memory.put(data.message)

    remote_run = remote_thread.run(
        assistant,
        event_handler_class=DefaultAssistantEventHandler,
        event_handler_kwargs={
            "context": context,
            "openai_run_id": data.run_id,
            "openai_thread_id": remote_thread.id,
            "openai_assistant_id": assistant.id,
            "memory": memory,
            "cache": extension_settings.storage.cache,
        },
        tool_choice="auto",
        tools=agent_config.get_assistant_tools(),
    )
    # save remote run id
    persisted_run = run_storage.get(data.run_id)
    if persisted_run:
        persisted_run.external_id = remote_run.run.id
        run_storage.update(persisted_run)

    send_close_event(data, "close")
    return remote_run


def handle_local_run(
    data: TriggerAgentRun,
    thread_storage: BaseThreadStore,
    run_storage: BaseRunStorage,
    context: dict,
    memory: Memory | None = None,
    chat_storage_class: type[BaseChatStore] | None = ChatStore,
):
    """
    Handle a single local run.
    Creates or fetches a local thread and run.
        - if storage is provided then the LocalThread class will use it.
    Create a run using the `LocalThread.run` method.

    Memory - use the same memory object for handler and thread
    ChatStorage - pass the chat storage to the memory class.
    ThreadStorage - pass the thread storage to the LocalThread class.
    """

    storage = chat_storage_class()
    memory = memory or memory_with_storage(data.thread_id, storage)
    # the agent to use
    assistant = data.agent_config.as_assistant()
    # add an event handler to save run data and streaming
    handler = DefaultAssistantEventHandler(
        context=context, cache=extension_settings.storage.cache, memory=memory
    )

    local_thread = LocalThread.create(
        id=data.thread_id,
        tenant_id=data.tenant_id,
        tags=data.tags,
        memory=memory,
        thread_storage=thread_storage,
    )
    local_thread.add_message(data.message)

    local_run = local_thread.run(
        assistant=assistant,
        context=context,
        event_handler=handler,
    )

    send_close_event(data, "close")
    return local_run


def start_run(data: TriggerAgentRun):
    """
    Create a new agent run
    This is usually triggered in a separate thread, therefore you need to set tenant_id
    """
    set_current_tenant_id(data.tenant_id)
    data = verify_runtime_config(data)
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
