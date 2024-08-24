# Marvin Django Apps

Extensions include modules to make it easier to integrate Marvin with Django.

- Integrate a new runner that is compatible with OPEN AI Assistants API but can work with ANY LLM.
- Use Django models to store chat history and messages.
- Custom event handler for streaming responses, and more.


### Use Django storage for threads, messages, and files

Assumes you have a Django model manager that implements the `BaseThreadStore`, `BaseChatStore`, and `BaseFileStore` interfaces.

Here are some examples from the starter kit.

#### Thread model

```python
from django.db import models
import marvin
from mavin.beta.assistants import Thread
from model_utils.models import TimeStampedModel, UUIDModel
from pydantic import BaseModel

from apps.tenants.models.mixins import TenantModelManagerMixin
from apps.tenants.utils import get_current_tenant_id


@marvin.fn(
    model_kwargs={"model": "gpt-4o-mini", "response_format": {"type": "json_object"}}
)
def trim_message(message: str):
    """
    Based on the message, provide an appropriate title for the thread.
    This must be 1 or two words.
    """

class ThreadManager(models.Manager, TenantModelManagerMixin):

    def trim_message(self, message: str):
        return trim_message(message)

    def add_thread(self, data: BaseModel):
        """
        Add a new thread to the database.
        """
        # skip this if latency is too high or add to a queue
        snippet = trim_message(data.message.content[0].text)
        tags = ["chat"]

        if data.agent_id:
            tags.append("agent")

        thread = self.create(
            name=snippet,
            tenant_id=data.tenant_id,
            user_id=data.user_id,
            id=data.thread_id,
            tags=tags,
        )
        return thread

    def list_threads(self, user_id):
        """
        List all threads for a given user
        """
        return self.filter(user_id=user_id).all()

    async def aget_or_add_thread(
        self, thread_id, tenant_id=None, tags=None, name=None, user_id=None
    ):
        """
        Fetch or create thread
        If mode is assistant, create a new thread in OpenAI
        """
        tenant_id = tenant_id or get_current_tenant_id()
        tags = tags or ["chat"]
        thread = await self.filter(id=thread_id).afirst()
        snippet = name[:50] if len(name) > 50 else name
        if not thread:
            thread = await self.acreate(
                id=thread_id,
                tenant_id=tenant_id,
                tags=tags,
                data={"snippet": name, "tagged": False},
                name=snippet or "New Chat",
                user_id=user_id,
            )
            trim_and_tag_thread_title_task.delay(name, thread.id, tenant_id)
        return thread

    def get_or_add_thread(
        self, thread_id, tenant_id=None, tags=None, name=None, user_id=None
    ):
        """
        Fetch or create thread
        If mode is assistant, create a new thread in OpenAI
        """
        tenant_id = tenant_id or get_current_tenant_id()
        tags = tags or ["chat"]
        thread = self.filter(id=thread_id).first()
        snippet = trim_message(name)
        if not thread:
            thread = self.create(
                id=thread_id,
                tenant_id=tenant_id,
                tags=tags,
                data={"snippet": name, "tagged": False},
                name=snippet or "New Chat",
                user_id=user_id,
            )
            trim_and_tag_thread_title_task.delay(name, thread.id, tenant_id)
        return thread

    def update_thread(self, data: BaseModel, thread=None):
        thread = thread or self.filter(id=data.thread_id).first()
        if not thread:
            return
        from apps.ai.models import DataSource

        docs = DataSource.objects.filter(file_id__in=data.document_ids)
        docs = [d.attachment_reference() for d in docs]
        if data.document_ids:
            thread.data["document_ids"] = data.document_ids
            thread.data["document_meta"] = [
                {"name": doc["metadata"]["name"], "type": doc["type"]} for doc in docs
            ]
            thread.tags = data.tags
            thread.user_id = data.user_id
            thread.save()
        return thread


class ChatThread(UUIDModel, TimeStampedModel):
    """
    Chat Thread model
    Keeps track of both internal and remote threads.
    - Avoid using FKeys on ai models to make scaling easier.
    """

    name = models.CharField(max_length=700, null=True, blank=True)
    tags = models.JSONField(null=True, blank=True)
    tenant_id = models.UUIDField(editable=False, null=True, blank=True)
    external_id = models.CharField(max_length=255, null=True, blank=True)
    user_id = models.CharField(max_length=255, null=True, blank=True)
    data = models.JSONField(null=True, blank=True)
    objects = ThreadManager()

    class Meta:
        verbose_name = "Thread"
        verbose_name_plural = "Threads"
        db_table = "ai_thread"
        abstract = False
        indexes = [
            models.Index(fields=["tenant_id", "user_id", "tags"]),
        ]

    def to_json(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "tenant_id": self.tenant_id,
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
            "external_id": self.external_id,
            "user_id": self.user_id,
            "tags": self.tags,
            "data": self.data,
        }

    def to_json_with_messages(self):
        """Retrieve all messages for a given thread"""
        from apps.ai.models.message import Message

        messages = Message.objects.list_thread_messages(self.id)
        return {
            **self.to_json(),
            "messages": [message.message for message in messages],
        }

    def add_message(self, data: BaseModel):
        """
        Add a message to the db thread and openai thread if external_id is set
        Currently not backwards compatible with old messages.
        """
        from apps.ai.models.message import Message

        # check if message has any attachments
        document_ids = None
        document_meta = None
        try:
            if data.metadata.attachments:
                document_ids = [attachment.id for attachment in data.attachments]
                document_meta = [
                    {
                        "name": attachment.name,
                        "type": attachment.type,
                    }
                    for attachment in data.attachments
                    if attachment.type in ["file"]
                ]
        except Exception:
            pass

        Message.objects.create_message(
            data,
            thread_id=self.id,
            tenant_id=self.tenant_id,
        )

        # update thread data
        thread_data = self.data or {}
        if document_ids:
            thread_data["document_ids"] = document_ids
        if document_meta:
            thread_data["document_meta"] = document_meta
        self.data = thread_data
        self.save()

    def remote_thread(self):
        if self.external_id:
            return Thread(id=self.external_id)
        else:
            thread = Thread()
            thread = thread.create()
            self.external_id = thread.id
            self.save()
            return thread
```


#### Message model

```python
import uuid

from django.db import models
from model_utils.models import TimeStampedModel, UUIDModel

from apps.ai.core.utilities.serialization import to_serializable


class MessageManager(models.Manager):
    def create_many(self, messages):
        for message in messages:
            self.create_message(**message)

    def create_message(self, data, thread_id, tenant_id, **kwargs):
        data = to_serializable(data)
        message = self.create(message=data, thread_id=thread_id, tenant_id=tenant_id)
        return message

    def create_or_update(self, data, thread_id, tenant_id, **kwargs):
        dict_data = to_serializable(data)
        message, _ = self.get_or_create(
            id=data.get("id", uuid.uuid4()),
            tenant_id=tenant_id,
            thread_id=thread_id,
            run_id=data.get("run_id"),
        )
        d = message.message or {}
        d.update(dict_data)
        message.message = d
        message.save()
        return message
    
    async def acreate_or_update(self, data, thread_id, tenant_id, **kwargs):
        dict_data = to_serializable(data)
        message, _ = await self.aget_or_create(
            id=data.get("id", uuid.uuid4()),
            tenant_id=tenant_id,
            thread_id=thread_id,
            run_id=data.get("run_id"),
        )
        d = message.message or {}
        d.update(dict_data)
        message.message = d
        await message.asave()
        return message
    
    def list_thread_messages(self, thread_id):
        return self.filter(thread_id=thread_id).all().order_by("created")


class Message(UUIDModel, TimeStampedModel):
    """
    Message model
    """

    data = models.JSONField("Metadata", null=True, blank=True)
    message = models.JSONField(
        "Message", null=True, blank=True, help_text="Message data only"
    )
    run_id = models.CharField(max_length=255, null=True, blank=True)
    tenant_id = models.UUIDField(editable=False, null=True, blank=True)
    thread_id = models.CharField(max_length=255, null=True, blank=True)
    external_id = models.CharField(max_length=255, null=True, blank=True)

    objects = MessageManager()

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        db_table = "ai_message"
        abstract = False

    def to_json(self):
        return {
            "id": str(self.id),
            "thread_id": self.thread_id,
            "tenant_id": self.tenant_id,
            "message": self.message,
            "created": self.created,
            "modified": self.modified,
        }

    def save_message_info(self, data):
        """
        Save message info
        Includes feedback
        """
        self.feedback = data.feedback
        self.save()

    def add_feedback(self, feedback, user_id):
        self.data = self.data or {}
        self.data["feedback"] = {
            "user_id": user_id,
            "feedback": feedback,
        }
        self.save()```
