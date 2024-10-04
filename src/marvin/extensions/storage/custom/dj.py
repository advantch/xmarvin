# import json
# import uuid
# import warnings
# from marvin.extensions.storage.data_source_store import BaseDataSourceStore
# from marvin.extensions.storage.message_store import BaseMessageStore
# from marvin.extensions.storage.thread_store import BaseThreadStore
# from marvin.extensions.storage.vector_store import BaseVectorStore
# from marvin.extensions.types.data_source import VectorStore
# from marvin.extensions.types.tools import AppCodeInterpreterTool, AppFileSearchTool, AppToolCall
# from marvin.extensions.tools.tool import Tool
# from marvin.extensions.utilities.serialization import to_serializable
# from marvin.extensions.storage.base import BaseStorage
# from marvin.extensions.types import ChatMessage, ChatThread, AgentConfig, DataSource, PersistedRun
# from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method
# from typing import List, Optional, Tuple, Any


# class DummyModels(object, *args, **kwargs):
#         class CharField(object, *args, **kwargs):
#             pass
#         class TextField(object, *args, **kwargs):
#             pass
#         class DateTimeField(object, *args, **kwargs):
#             pass
#         class ForeignKey(object, *args, **kwargs):
#             pass
#         class OneToOneField(object, *args, **kwargs):
#             pass
#         class UUIDField(object, *args, **kwargs):
#             pass
# models = DummyModels()

# # try:

# # except ImportError:
# #     warnings.warn("Install django to use this module")


# class CustomJSONField(models.TextField):
#     def from_db_value(self, value, expression, connection):
#         if value is None:
#             return value
#         return json.loads(value)

#     def to_python(self, value):
#         if isinstance(value, str):
#             return json.loads(value)
#         return value

#     def get_prep_value(self, value):
#         return json.dumps(to_serializable(value))

# class BaseThreadModel(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     tenant_id = models.CharField(max_length=255, null=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     metadata = models.TextField(null=True)
#     model_data = models.JSONField(null=True)

#     class Meta:
#         abstract = True

# class BaseMessageModel(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     thread_id = models.CharField(max_length=255)
#     role = models.CharField(max_length=50)
#     content = models.TextField()
#     created_at = models.DateTimeField(auto_now_add=True)
#     metadata = models.TextField(null=True)
#     model_data = models.JSONField(null=True)

#     class Meta:
#         abstract = True

# class BaseAgentModel(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     name = models.CharField(max_length=255)
#     description = models.TextField(null=True)
#     instructions = models.TextField(null=True)
#     model = models.CharField(max_length=255)
#     tools = models.TextField(null=True)
#     metadata = models.TextField(null=True)
#     model_data = models.JSONField(null=True)

#     class Meta:
#         abstract = True

# class BaseRunModel(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     thread_id = models.CharField(max_length=255, null=True)
#     tenant_id = models.CharField(max_length=255, null=True)
#     agent_id = models.CharField(max_length=255, null=True)
#     status = models.CharField(max_length=50)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     external_id = models.CharField(max_length=255, null=True)
#     data = models.TextField(null=True)
#     tags = models.TextField(null=True)
#     model_data = models.JSONField(null=True)

#     class Meta:
#         abstract = True

# class BaseDataSourceModel(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     name = models.CharField(max_length=255)
#     description = models.TextField(null=True)
#     type = models.CharField(max_length=50, null=True, default="file")
#     metadata = models.TextField(null=True)
#     model_data = models.JSONField(null=True)

#     class Meta:
#         abstract = True

# class BaseToolModel(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     name = models.CharField(max_length=255)
#     description = models.TextField()
#     function = models.TextField()
#     parameters = models.TextField(null=True)
#     model_data = models.JSONField(null=True)

#     class Meta:
#         abstract = True


# class DjangoMessageStore(BaseMessageStore):
#     def __init__(self, model):
#         self.model = model

#     @expose_sync_method("save")
#     async def save_async(self, message: ChatMessage) -> None:
#         await self.model.objects.update_or_create(
#             id=message.id, defaults=message.model_dump()
#         )

#     @expose_sync_method("get")
#     async def get_async(self, message_id: str) -> Optional[ChatMessage]:
#         message = await self.model.objects.filter(id=message_id).first()
#         return ChatMessage.model_validate(message) if message else None

#     @expose_sync_method("list")
#     async def list_async(
#         self, filter_params: Optional[dict] = None
#     ) -> List[ChatMessage]:
#         queryset = self.model.objects.all()
#         if filter_params:
#             queryset = queryset.filter(**filter_params)
#         messages = await queryset
#         return [ChatMessage.model_validate(message) for message in messages]

#     @expose_sync_method("get_thread_messages")
#     async def get_thread_messages_async(self, thread_id: str) -> List[ChatMessage]:
#         queryset = self.model.objects.filter(thread_id=thread_id)
#         messages = await queryset
#         return [ChatMessage.model_validate(message) for message in messages]


#     @expose_sync_method("update_message_tool_calls")
#     async def update_message_tool_calls_async(
#         self,
#         thread_id: str,
#         file_id: str,
#         data_source
#     ) -> None:
#         """
#         Update the tool calls for a message.
#         """
#         messages = self.model.objects.filter(thread_id=thread_id, metadata__tool_calls__code_interpreter__isnull=False)
#         for message in messages:
#             chat_message = ChatMessage.model_validate(message.model_data)
#             if chat_message.metadata.tool_calls:
#                 tc = []
#                 for tool_call in chat_message.metadata.tool_calls:
#                     if getattr(tool_call, "code_interpreter", None):
#                         for output in tool_call.code_interpreter.outputs:
#                             if getattr(output, "image", None):
#                                 if output.image.file_id == file_id:

#                                     tool_call.structured_output = {
#                                         "type": "image_url",
#                                         "image_url": {
#                                             "url": data_source.url
#                                         }
#                                     }

#                     if tool_call.type == "code_interpreter":
#                         tool_call = AppCodeInterpreterTool.model_validate(tool_call.model_dump())
#                     if tool_call.type == "file_search":
#                         tool_call = AppFileSearchTool.model_validate(tool_call.model_dump())
#                     if tool_call.type == "function":
#                         tool_call = AppToolCall.model_validate(tool_call.model_dump())
#                     tc.append(tool_call)
#                 chat_message.metadata.tool_calls = tc
#                 ChatMessage.model_rebuild()
#                 message.model_data = chat_message.model_dump()
#                 message.save()


# class DjangoThreadStore(BaseThreadStore):
#     def __init__(self, model):
#         self.model = model

#     @expose_sync_method("save_thread")
#     async def save_thread_async(self, thread: ChatThread) -> None:
#         await self.model.objects.update_or_create(
#             id=thread.id, defaults=thread.model_dump()
#         )

#     @expose_sync_method("get_thread")
#     async def get_thread_async(
#         self, thread_id: str, tenant_id: str | None = None
#     ) -> Optional[ChatThread]:
#         thread = await self.model.objects.filter(
#             id=thread_id, tenant_id=tenant_id
#         ).first()
#         return ChatThread.model_validate(thread) if thread else None

#     @expose_sync_method("get_or_create_thread")
#     async def get_or_create_thread_async(
#         self, thread_id: str, tenant_id: str | None = None
#     ) -> ChatThread:
#         thread = await self.model.objects.filter(
#             id=thread_id, tenant_id=tenant_id
#         ).first()
#         if not thread:
#             thread = ChatThread(id=thread_id, tenant_id=tenant_id)
#             await self.save_thread_async(thread)
#         return thread

#     @expose_sync_method("list_threads")
#     async def list_threads_async(
#         self, filter_params: Optional[dict] = None, tenant_id: str | None = None
#     ) -> List[ChatThread]:
#         queryset = self.model.objects.filter(tenant_id=tenant_id)
#         if filter_params:
#             queryset = queryset.filter(**filter_params)
#         threads = await queryset
#         return [ChatThread.model_validate(thread) for thread in threads]


# class DjangoAgentStore(BaseStorage[AgentConfig], ExposeSyncMethodsMixin):
#     def __init__(self, model):
#         self.model = model

#     @expose_sync_method("save_agent")
#     async def save_agent_async(self, agent: AgentConfig) -> None:
#         await self.model.objects.update_or_create(
#             id=agent.id, defaults=agent.model_dump()
#         )

#     @expose_sync_method("get_agent")
#     async def get_agent_async(self, agent_id: str) -> Optional[AgentConfig]:
#         agent = await self.model.objects.filter(id=agent_id).first()
#         return AgentConfig.model_validate(agent) if agent else None

#     @expose_sync_method("list_agents")
#     async def list_agents_async(
#         self, filter_params: Optional[dict] = None
#     ) -> List[AgentConfig]:
#         queryset = self.model.objects.all()
#         if filter_params:
#             queryset = queryset.filter(**filter_params)
#         agents = await queryset
#         return [AgentConfig.model_validate(agent) for agent in agents]


# class DjangoToolStore(BaseStorage[Tool], ExposeSyncMethodsMixin):
#     def __init__(self, model):
#         self.model = model

#     @expose_sync_method("save_tool")
#     async def save_tool_async(self, tool: Tool) -> None:
#         await self.model.objects.update_or_create(
#             id=tool.id, defaults=tool.model_dump()
#         )

#     @expose_sync_method("get_tool")
#     async def get_tool_async(self, tool_id: str) -> Optional[Tool]:
#         tool = await self.model.objects.filter(id=tool_id).first()
#         return Tool.model_validate(tool) if tool else None

#     @expose_sync_method("list_tools")
#     async def list_tools_async(
#         self, filter_params: Optional[dict] = None
#     ) -> List[Tool]:
#         queryset = self.model.objects.all()
#         if filter_params:
#             queryset = queryset.filter(**filter_params)
#         tools = await queryset
#         return [Tool.model_validate(tool) for tool in tools]


# class DjangoDataSourceStore(BaseDataSourceStore):
#     def __init__(self, model):
#         self.model = model

#     @expose_sync_method("save_data_source")
#     async def save_data_source_async(self, data_source: DataSource) -> DataSource:
#         await self.model.objects.update_or_create(
#             id=data_source.id, defaults={"model_data": data_source.model_dump()}
#         )

#     @expose_sync_method("get_data_source")
#     async def get_data_source_async(self, data_source_id: str) -> Optional[DataSource]:
#         data_source = await self.model.objects.filter(id=data_source_id).first()
#         return DataSource.model_validate(data_source.model_data) if data_source else None

#     @expose_sync_method("list_data_sources")
#     async def list_data_sources_async(
#         self, filter_params: Optional[dict] = None
#     ) -> List[DataSource]:
#         queryset = self.model.objects.all()
#         if filter_params:
#             queryset = queryset.filter(**filter_params)
#         data_sources = await queryset
#         return [DataSource.model_validate(ds.model_data) for ds in data_sources]

#     @expose_sync_method("get_file_content_by_file_id")
#     async def get_file_content_by_file_id_async(self, file_id: str) -> Optional[str]:
#         data_source = await self.model.objects.filter(
#             file_store_metadata__file_id=file_id
#         ).first()
#         if not data_source:
#             return None
#         if data_source.model_data.upload:
#             return data_source.upload.content
#         return None


# class DjangoRunStore(BaseStorage[PersistedRun], ExposeSyncMethodsMixin):
#     def __init__(self, model):
#         self.model = model

#     @expose_sync_method("save_run")
#     async def save_run_async(self, run: PersistedRun) -> None:
#         await self.model.objects.update_or_create(id=run.id, defaults=run.model_dump())

#     @expose_sync_method("get_run")
#     async def get_run_async(self, run_id: str) -> Optional[PersistedRun]:
#         run = await self.model.objects.filter(id=run_id).first()
#         return PersistedRun.model_validate(run) if run else None

#     @expose_sync_method("list_runs")
#     async def list_runs_async(
#         self, filter_params: Optional[dict] = None
#     ) -> List[PersistedRun]:
#         queryset = self.model.objects.all()
#         if filter_params:
#             queryset = queryset.filter(**filter_params)
#         runs = await queryset
#         return [PersistedRun.model_validate(run) for run in runs]

#     @expose_sync_method("get_or_create")
#     async def get_or_create_async(self, id: str) -> Tuple[PersistedRun, bool]:
#         run, created = await self.model.objects.get_or_create(id=id)
#         return PersistedRun.model_validate(run), created

#     @expose_sync_method("init_db_run")
#     async def init_db_run_async(
#         self,
#         run_id: str,
#         thread_id: str | None = None,
#         tenant_id: str | None = None,
#         remote_run: Any = None,
#         agent_id: str | None = None,
#         user_message: str | None = None,
#         tags: List[str] | None = None,
#     ) -> PersistedRun:
#         run, created = await self.get_or_create_async(run_id)
#         if created:
#             run.thread_id = thread_id
#             run.tenant_id = tenant_id
#             run.agent_id = agent_id
#             run.status = "started"
#             if user_message:
#                 run.data["user_message"] = user_message
#             if tags:
#                 run.tags = tags
#         if remote_run:
#             run.external_id = remote_run.id
#         await self.save_run_async(run)
#         return run


# class DjangoVectorStore(BaseVectorStore):
#     def __init__(self, model):
#         self.model = model

#     @expose_sync_method("save_vector")
#     async def save_vector_async(self, vector_store: VectorStore) -> None:
#         await self.model.objects.aupdate_or_create(
#             id=vector_store.id, defaults=vector_store.model_dump()
#         )

#     @expose_sync_method("get_vector")
#     async def get_vector_async(self, vector_store_id: str) -> Optional[VectorStore]:
#         vector_store = await self.model.objects.filter(id=vector_store_id).first()
#         return VectorStore.model_validate(vector_store) if vector_store else None

#     @expose_sync_method("list_vectors")
#     async def list_vectors_async(
#         self, filter_params: Optional[dict] = None
#     ) -> List[VectorStore]:
#         queryset = self.model.objects.all()
#         if filter_params:
#             queryset = queryset.filter(**filter_params)
#         vector_stores = await queryset
#         return [VectorStore.model_validate(vs) for vs in vector_stores]
