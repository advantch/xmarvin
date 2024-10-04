import json
from datetime import datetime
from typing import Any, List, Optional

from peewee import CharField, DateTimeField, Model, SqliteDatabase, TextField

from marvin.extensions.storage import (
    BaseAgentStore,
    BaseDataSourceStore,
    BaseMessageStore,
    BaseRunStore,
    BaseThreadStore,
    BaseToolStore,
)
from marvin.extensions.tools.tool import Tool
from marvin.extensions.types import (
    AgentConfig,
    ChatMessage,
    ChatThread,
    DataSource,
    PersistedRun,
)
from marvin.extensions.types.tools import (
    AppCodeInterpreterTool,
    AppFileSearchTool,
    AppToolCall,
)
from marvin.extensions.utilities.logging import pretty_log
from marvin.extensions.utilities.serialization import to_serializable
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method

_db_path = "marvin.db"
db = SqliteDatabase(_db_path)


class CustomJSONField(TextField):
    def python_value(self, value):
        if value is None:
            return None
        return json.loads(value)

    def db_value(self, value):
        if value is None:
            return None
        return json.dumps(to_serializable(value))


class BaseModel(Model):
    model_data = CustomJSONField(null=True)

    class Meta:
        database = db


class ThreadModel(BaseModel):
    id = CharField(primary_key=True)
    tenant_id = CharField(null=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    metadata = TextField(null=True)

    class Meta:
        table_name = "threads"
        database = db


class MessageModel(BaseModel):
    id = CharField(primary_key=True)
    thread_id = CharField()
    role = CharField()
    content = TextField()
    created_at = DateTimeField(default=datetime.utcnow)
    metadata = TextField(null=True)

    class Meta:
        table_name = "messages"
        database = db


class AgentModel(BaseModel):
    id = CharField(primary_key=True)
    name = CharField()
    description = TextField(null=True)
    instructions = TextField(null=True)
    model = CharField()
    tools = TextField(null=True)
    metadata = TextField(null=True)

    class Meta:
        table_name = "agents"
        database = db


class RunModel(BaseModel):
    id = CharField(primary_key=True)
    thread_id = CharField(null=True)
    tenant_id = CharField(null=True)
    agent_id = CharField(null=True)
    status = CharField()
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    external_id = CharField(null=True)
    data = TextField(null=True)
    tags = TextField(null=True)

    class Meta:
        table_name = "runs"
        database = db


class DataSourceModel(BaseModel):
    id = CharField(primary_key=True)
    name = CharField()
    description = TextField(null=True)
    type = CharField(null=True, default="file")
    metadata = TextField(null=True)

    class Meta:
        table_name = "data_sources"
        database = db


class ToolModel(BaseModel):
    id = CharField(primary_key=True)
    name = CharField()
    description = TextField()
    function = TextField()
    parameters = TextField(null=True)

    class Meta:
        table_name = "tools"
        database = db


class PeeweeThreadStore(BaseThreadStore, ExposeSyncMethodsMixin):
    @expose_sync_method("save_thread")
    async def save_thread_async(self, thread: ChatThread) -> None:
        t, created = ThreadModel.get_or_create(
            id=thread.id,
            defaults={
                "tenant_id": thread.tenant_id,
                "metadata": thread.model_dump(),
                "model_data": thread.model_dump(),
            },
        )
        if not created:
            t.model_data = thread.model_dump()
            t.save()

    @expose_sync_method("get_thread")
    async def get_thread_async(
        self, thread_id: str, tenant_id: str | None = None
    ) -> Optional[ChatThread]:
        try:
            thread = ThreadModel.get(
                ThreadModel.id == thread_id, ThreadModel.tenant_id == tenant_id
            )
            chat_thread = ChatThread.model_validate(thread.model_data)
            return chat_thread
        except ThreadModel.DoesNotExist:
            return None

    @expose_sync_method("get_or_create_thread")
    async def get_or_create_thread_async(
        self, thread_id: str, tenant_id: str | None = None
    ) -> ChatThread:
        thread, created = ThreadModel.get_or_create(
            id=thread_id,
        )
        if created:
            chat_thread = ChatThread(id=thread_id, tenant_id=tenant_id)
            thread.tenant_id = tenant_id
            thread.model_data = chat_thread.model_dump()
            thread.save()

        return ChatThread.model_validate(thread.model_data)

    @expose_sync_method("list_threads")
    async def list_threads_async(
        self, filter_params: Optional[dict] = None, tenant_id: str | None = None
    ) -> List[ChatThread]:
        query = ThreadModel.select()
        if tenant_id:
            query = query.where(ThreadModel.tenant_id == tenant_id)
        if filter_params:
            for key, value in filter_params.items():
                query = query.where(getattr(ThreadModel, key) == value)
        return [ChatThread.model_validate(thread.model_data or {}) for thread in query]


class PeeweeMessageStore(BaseMessageStore, ExposeSyncMethodsMixin):
    @expose_sync_method("save")
    async def save_async(self, message: ChatMessage, thread_id) -> None:
        message_model, created = MessageModel.get_or_create(
            id=message.id,
            defaults={
                "thread_id": thread_id,
                "role": message.role,
                "content": message.content,
                "metadata": message.metadata.model_dump() if message.metadata else None,
                "model_data": message.model_dump(),
            },
        )
        if not created:
            message_model.model_data = message.model_dump()
            message_model.save()

    @expose_sync_method("get")
    async def get_async(self, message_id: str) -> Optional[ChatMessage]:
        try:
            message = MessageModel.get(MessageModel.id == message_id)
            return ChatMessage.model_validate(message.model_data)
        except MessageModel.DoesNotExist:
            return None

    @expose_sync_method("list")
    async def list_async(self, thread_id: str) -> List[ChatMessage]:
        query = MessageModel.select().where(MessageModel.thread_id == thread_id)
        return [ChatMessage.model_validate(message.model_data) for message in query]

    @expose_sync_method("get_thread_messages")
    async def get_thread_messages_async(self, thread_id: str) -> List[ChatMessage]:
        messages = MessageModel.select().where(MessageModel.thread_id == thread_id)
        return [ChatMessage.model_validate(message.model_data) for message in messages]

    @expose_sync_method("update_message_tool_calls")
    async def update_message_tool_calls_async(
        self,
        thread_id,
        file_id,
        data_source,
    ) -> None:
        messages = MessageModel.filter(MessageModel.thread_id == thread_id)
        for message in messages:
            chat_message = ChatMessage.model_validate(message.model_data)
            if chat_message.metadata.tool_calls:
                tc = []
                for tool_call in chat_message.metadata.tool_calls:
                    if getattr(tool_call, "code_interpreter", None):
                        for output in tool_call.code_interpreter.outputs:
                            if getattr(output, "image", None):
                                if output.image.file_id == file_id:
                                    pretty_log("is file id")

                                    tool_call.structured_output = {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": data_source.file_store_metadata.url,
                                            "presigned_url": data_source.file_store_metadata.presigned_url,
                                        },
                                    }

                    if tool_call.type == "code_interpreter":
                        tool_call = AppCodeInterpreterTool.model_validate(
                            tool_call.model_dump()
                        )
                    if tool_call.type == "file_search":
                        tool_call = AppFileSearchTool.model_validate(
                            tool_call.model_dump()
                        )
                    if tool_call.type == "function":
                        tool_call = AppToolCall.model_validate(tool_call.model_dump())
                    tc.append(tool_call)
                chat_message.metadata.tool_calls = tc
                ChatMessage.model_rebuild()
                message.model_data = chat_message.model_dump()
                message.save()


class PeeweeAgentStore(BaseAgentStore, ExposeSyncMethodsMixin):
    @expose_sync_method("save")
    async def save_async(self, agent: AgentConfig) -> None:
        agent_model, created = AgentModel.get_or_create(
            id=agent.id,
            defaults={
                "name": agent.name,
                "description": agent.description,
                "instructions": agent.instructions,
                "model": agent.model,
                "tools": ",".join(agent.tools) if agent.tools else None,
                "model_data": agent.model_dump(),
            },
        )
        if not created:
            agent_model.model_data = agent.model_dump()
            agent_model.save()

    @expose_sync_method("get")
    async def get_async(self, agent_id: str) -> Optional[AgentConfig]:
        try:
            agent = AgentModel.get(AgentModel.id == agent_id)
            return AgentConfig.model_validate(agent.model_data)
        except AgentModel.DoesNotExist:
            return None

    @expose_sync_method("list")
    async def list_async(
        self, filter_params: Optional[dict] = None
    ) -> List[AgentConfig]:
        query = AgentModel.select()
        if filter_params:
            for key, value in filter_params.items():
                query = query.where(getattr(AgentModel, key) == value)
        return [AgentConfig.model_validate(agent.model_data) for agent in query]


class PeeweeRunStore(BaseRunStore, ExposeSyncMethodsMixin):
    @expose_sync_method("save_run")
    async def save_run_async(self, run: PersistedRun) -> None:
        run_model, _ = RunModel.get_or_create(
            id=run.id,
        )
        run_model.model_data = run.model_dump()
        run_model.save()

    @expose_sync_method("get_run")
    async def get_run_async(self, run_id: str) -> Optional[PersistedRun]:
        try:
            run = RunModel.get(RunModel.id == run_id)
            print(f"Run {run.id} found, {run.model_data}")
            return PersistedRun.model_validate(run.model_data)
        except RunModel.DoesNotExist:
            return None

    @expose_sync_method("list_runs")
    async def list_runs_async(
        self, filter_params: Optional[dict] = None
    ) -> List[PersistedRun]:
        query = RunModel.select()
        if filter_params:
            for key, value in filter_params.items():
                query = query.where(getattr(RunModel, key) == value)
        return [PersistedRun.model_validate(run.model_data) for run in query]

    @expose_sync_method("get_or_create")
    async def get_or_create_async(self, id: str) -> tuple[PersistedRun, bool]:
        run, created = RunModel.get_or_create(id=id)
        return PersistedRun.model_validate(run.model_data), created

    @expose_sync_method("init_db_run")
    async def init_db_run_async(
        self,
        run_id: str,
        thread_id: str | None = None,
        tenant_id: str | None = None,
        remote_run: Any = None,
        agent_id: str | None = None,
        user_message: str | None = None,
        tags: List[str] | None = None,
    ) -> PersistedRun:
        persisted_run = PersistedRun(
            id=run_id,
            thread_id=thread_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            status="started",
            data={"user_message": user_message} if user_message else None,
            tags=tags if tags else None,
        )

        run_model, created = RunModel.get_or_create(
            id=run_id,
            defaults={
                "status": "started",
            },
        )
        print(f"Run {run_model.id} created: {created}")
        run_model.model_data = persisted_run.model_dump()

        if remote_run:
            run_model.external_id = remote_run.id
        run_model.save()
        return PersistedRun.model_validate(run_model.model_data)


class PeeweeDataSourceStore(BaseDataSourceStore, ExposeSyncMethodsMixin):
    @expose_sync_method("save_data_source")
    async def save_data_source_async(self, data_source: DataSource) -> None:
        data_source_model, created = DataSourceModel.get_or_create(
            id=data_source.id,
            defaults={
                "name": data_source.name,
                "description": data_source.description,
                "metadata": data_source.metadata,
                "model_data": data_source.model_dump(),
            },
        )
        if not created:
            data_source_model.model_data = data_source.model_dump()
            data_source_model.save()
        return DataSource.model_validate(data_source_model.model_data)

    @expose_sync_method("get_data_source")
    async def get_data_source_async(self, data_source_id: str) -> Optional[DataSource]:
        try:
            ds = DataSourceModel.get(DataSourceModel.id == data_source_id)
            return DataSource.model_validate(ds.model_data)
        except DataSourceModel.DoesNotExist:
            return None

    @expose_sync_method("list_data_sources")
    async def list_data_sources_async(
        self, filter_params: Optional[dict] = None
    ) -> List[DataSource]:
        query = DataSourceModel.select()
        if filter_params:
            for key, value in filter_params.items():
                query = query.where(getattr(DataSourceModel, key) == value)
        return [DataSource.model_validate(ds.model_data) for ds in query]


class PeeweeToolStore(BaseToolStore, ExposeSyncMethodsMixin):
    @expose_sync_method("save_tool")
    async def save_tool_async(self, tool: Tool) -> None:
        tool_model, created = ToolModel.get_or_create(
            id=tool.id,
            defaults={
                "name": tool.name,
                "description": tool.description,
                "function": tool.function,
                "parameters": tool.parameters.json() if tool.parameters else None,
                "model_data": tool.model_dump(),
            },
        )
        if not created:
            tool_model.model_data = tool.model_dump()
            tool_model.save()

    @expose_sync_method("get_tool")
    async def get_tool_async(self, tool_id: str) -> Optional[Tool]:
        try:
            tool = ToolModel.get(ToolModel.id == tool_id)
            return Tool.model_validate(tool.model_data)
        except ToolModel.DoesNotExist:
            return None

    @expose_sync_method("list_tools")
    async def list_tools_async(
        self, filter_params: Optional[dict] = None
    ) -> List[Tool]:
        query = ToolModel.select()
        if filter_params:
            for key, value in filter_params.items():
                query = query.where(getattr(ToolModel, key) == value)
        return [Tool.model_validate(tool.model_data) for tool in query]


db.connect()
# run migraions
# from playhouse.migrate import SqliteMigrator, migrate
# migrator = SqliteMigrator(db)
# try:
#     for m in [ThreadModel, MessageModel, AgentModel, RunModel, DataSourceModel, ToolModel]:
#         migrator.add_column(m, "model_data", TextField(null=True))
# except Exception as e:
#     print(f"Error migrating SQLite database: {e}")


def init_sqlite_db(db_path: str | None = None):
    try:
        db.create_tables(
            [
                ThreadModel,
                MessageModel,
                AgentModel,
                RunModel,
                DataSourceModel,
                ToolModel,
            ]
        )

    except Exception as e:
        print(f"Error initializing SQLite database: {e}")
