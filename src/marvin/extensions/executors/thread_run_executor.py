"""
Runners for agents.
Used to
    - create the context for the run.
    - ensures all tools, agents, components are available in context

"""

import asyncio
import traceback

import rich

from marvin.beta.assistants import Assistant
from marvin.beta.assistants.threads import Thread
from marvin.beta.local.handlers import (
    DefaultAssistantEventHandler,
)
from marvin.beta.local.thread import LocalThread
from marvin.extensions.context.run_context import (
    RunContext,
    RunContextStores,
)
from marvin.extensions.context.tenant import (
    get_current_tenant_id,
    set_current_tenant_id,
)
from marvin.extensions.memory.runtime_memory import RuntimeMemory
from marvin.extensions.settings import update_marvin_settings
from marvin.extensions.storage import (
    BaseAgentStore,
    BaseRunStore,
)
from marvin.extensions.types import ChatMessage
from marvin.extensions.types.agent import AgentConfig
from marvin.extensions.types.start_run import TriggerAgentRun
from marvin.extensions.utilities.assistants_api import create_thread_message
from marvin.extensions.utilities.configure_preset import configure_internal_sql_agent
from marvin.extensions.utilities.logging import logger
from marvin.extensions.utilities.message_parsing import (
    get_openai_assistant_attachments,
    get_openai_assistant_messages,
)
from marvin.extensions.utilities.setup_storage import setup_memory_stores
from marvin.extensions.utilities.streaming import send_app_event


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


async def verify_runtime_config(
    data: TriggerAgentRun,
    agent_storage: BaseAgentStore,
):
    """
    Validate and configure runtime config for agent.
    Fetch db agent if available and id provided.
    - add any additional context
    - fetch and add tools and related configs.
    Existing config will not be overwritten.

    # TODO: support for fetching remote agents?
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
        agent_config = await agent_storage.get_async(data.agent_id)
        data.agent_config = agent_config or default_config

    if data.runtime_config:
        # addition context is used in templates during instruction parsing
        data.agent_config.runtime_config = data.runtime_config

        # handle model overrides
        if data.agent_config.runtime_config.model:
            data.agent_config.model = data.agent_config.runtime_config.model

    return data


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


def initialise_run(data: TriggerAgentRun, run_store: BaseRunStore):
    """
    Initialise a run in storage.
    Required if not using `handle_assistant_run` or `handle_local_run` or `start_run` method.
    """
    persisted_run = run_store.get_run(data.run_id)
    if not persisted_run:
        persisted_run = run_store.init_db_run(
            run_id=data.run_id,
            thread_id=data.thread_id,
            tenant_id=data.tenant_id,
            agent_id=data.agent_id,
            tags=data.tags or ["chat", "agent"],
        )
    return persisted_run


async def initialise_run_async(data: TriggerAgentRun, run_store: BaseRunStore):
    """
    Initialise a run in storage.
    """
    persisted_run = await run_store.init_db_run_async(
        run_id=data.run_id,
        thread_id=data.thread_id,
        tenant_id=data.tenant_id,
        agent_id=data.agent_id,
        tags=data.tags or ["chat", "agent"],
    )
    await run_store.save_run_async(persisted_run)
    return persisted_run


async def handle_assistant_run(
    data: TriggerAgentRun,
    context_stores: RunContextStores | None = None,
    context: dict | None = None,
):
    """
    Handle a single assistant run.
    A run is a complete execution that may span multiple llm calls and tools calls.
    A run terminates when it is stopped or the llm call is completed.

    @param data: TriggerAgentRun
    @param context_storage: BaseContextStorage -
    @param context: dict
    """
    # initialise settings
    update_marvin_settings()
    tenant_id = data.tenant_id or get_current_tenant_id()

    # setup stores
    context_stores = context_stores or setup_memory_stores()
    await initialise_run_async(data, context_stores.run_store)

    with RunContext(
        channel_id=data.channel_id,
        run_id=data.run_id,
        thread_id=data.thread_id,
        tenant_id=data.tenant_id,
        agent_config=data.agent_config,
        stores=context_stores,
        runtime_memory=RuntimeMemory(
            storage=context_stores.message_store,
            index=data.thread_id,
            thread_id=data.thread_id,
        ),
    ) as run_ctx:
        # initialise any storage

        chat_thread = await context_stores.thread_store.get_or_create_thread_async(
            data.thread_id, tenant_id=tenant_id
        )

        # fetch the remote thread
        if chat_thread.external_id:
            remote_thread = Thread(id=chat_thread.external_id)
        else:
            remote_thread = Thread()
            remote_thread = await remote_thread.create_async()
            chat_thread.external_id = remote_thread.id

            await context_stores.thread_store.save_thread_async(chat_thread)

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
        await run_ctx.runtime_memory.put_async(data.message)

        # run the assistant
        # setup the event handler with the required args
        remote_run = await remote_thread.run_async(
            assistant,
            event_handler_class=DefaultAssistantEventHandler,
            event_handler_kwargs={
                "context": run_ctx,
                "openai_run_id": data.run_id,
                "openai_thread_id": remote_thread.id,
                "openai_assistant_id": assistant.id,
                "memory": run_ctx.runtime_memory,
                "cache": run_ctx.cache_store,
            },
            tool_choice="auto",
            tools=agent_config.get_assistant_tools(),
        )

        # save remote run id
        run_store = run_ctx.stores.run_store
        persisted_run = await run_store.get_run_async(data.run_id)
        if persisted_run:
            persisted_run.external_id = remote_run.run.id
            await run_store.save_run_async(persisted_run)

        send_close_event(data, "close")
        return remote_run


async def handle_local_run(
    data: TriggerAgentRun,
    context_stores: RunContextStores | None = None,
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
    update_marvin_settings()
    tenant_id = data.tenant_id or get_current_tenant_id()
    context_stores = context_stores or setup_memory_stores()
    await initialise_run_async(data, context_stores.run_store)
    with RunContext(
        channel_id=data.channel_id,
        run_id=data.run_id,
        thread_id=data.thread_id,
        tenant_id=data.tenant_id,
        agent_config=data.agent_config,
        stores=context_stores,
    ) as run_ctx:
        await context_stores.thread_store.get_or_create_thread_async(
            data.thread_id, tenant_id=tenant_id
        )

        storage = context_stores.message_store
        memory = RuntimeMemory(
            storage=storage,
            index=data.thread_id,
            thread_id=data.thread_id,
        )
        # the agent to use
        assistant = data.agent_config.as_assistant()
        assert run_ctx is not None
        # add an event handler to save run data and streaming
        handler = DefaultAssistantEventHandler(
            context=run_ctx, cache=run_ctx.cache_store, memory=memory
        )

        local_thread = await LocalThread.create_async(
            id=data.thread_id,
            tenant_id=data.tenant_id,
            tags=data.tags,
            memory=memory,
            thread_storage=context_stores.thread_store,
        )
        local_thread.add_message(data.message)

        local_run = await local_thread.run_async(
            assistant=assistant,
            context=run_ctx,
            event_handler=handler,
            id=data.run_id,
        )

        send_close_event(data, "close")
        return local_run


async def start_run(
    data: TriggerAgentRun, context_stores: RunContextStores | None = None
):
    """
    Create a new agent run
    This is usually triggered in a separate thread, therefore you need to set tenant_id
    """
    set_current_tenant_id(data.tenant_id)
    context_stores = context_stores or setup_memory_stores()

    data = await verify_runtime_config(data, context_stores.agent_store)
    try:
        if data.agent_config.mode == "assistant":
            return await handle_assistant_run(data, context_stores)
        else:
            return await handle_local_run(data, context_stores)

    # capture asyncio error
    except asyncio.CancelledError as e:
        logger.error(f"Error executing agent run cancelled: {e}")
        send_close_event(data, "error", e)

    except Exception as e:
        logger.error(f"Error executing agent run: {e}")
        traceback.print_exc()
        send_close_event(data, "error", e)
