from typing import TYPE_CHECKING, Any, Dict, List, Optional

from openai import NotFoundError
from openai.types.beta.threads import Message
from openai.types.beta.vector_store import VectorStore
from openai.types.beta.vector_stores import VectorStoreFile
from pydantic import BaseModel, Field

import marvin.utilities.openai
from marvin.extensions.types.message import (
    ChatMessage,
)
from marvin.extensions.utilities.file_utilities import ContentFile
from marvin.utilities.asyncio import (
    ExposeSyncMethodsMixin,
    expose_sync_method,
    run_sync,
)
from marvin.utilities.logging import get_logger

logger = get_logger("Threads")

if TYPE_CHECKING:
    from .assistants import Assistant
    from .runs import Run


class Thread(BaseModel, ExposeSyncMethodsMixin):
    """
    The Thread class represents a conversation thread with an assistant.

    Attributes:
        id (Optional[str]): The unique identifier of the thread. None if the thread
                            hasn't been created yet.
        metadata (dict): Additional data about the thread.
    """

    id: Optional[str] = None
    metadata: dict = {}
    messages: list[Message] = Field([], repr=False)
    vector_store_id: Optional[str] = None

    def __enter__(self):
        return run_sync(self.__aenter__)

    def __exit__(self, exc_type, exc_val, exc_tb):
        return run_sync(self.__aexit__, exc_type, exc_val, exc_tb)

    async def __aenter__(self):
        await self.create_async()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.delete_async()
        return False

    @expose_sync_method("create")
    async def create_async(self, messages: list[str] = None):
        """
        Creates a thread.
        """
        if self.id is not None:
            raise ValueError("Thread has already been created.")
        if messages is not None:
            messages = [{"role": "user", "content": message} for message in messages]
        client = marvin.utilities.openai.get_openai_client()
        response = await client.beta.threads.create(messages=messages)
        self.id = response.id
        return self

    @expose_sync_method("get_or_create")
    async def get_or_create_async(self):
        """
        Get or create a thread.
        """
        client = marvin.utilities.openai.get_openai_client()
        try:
            await client.beta.threads.retrieve(thread_id=self.id)

        except NotFoundError:
            thread = await self.create_async()
            self.id = thread.id
            return thread

    @expose_sync_method("add_formatted_message")
    async def add_formatted_message_async(
        self,
        content: List[Dict[str, Any]],
        role: str = "user",
        attachments: List[Dict[str, Any]] = None,
        formatted_image_files: List[Dict[str, Any]] = None,
    ):
        """
        Add a formatted message to the thread.
        """
        client = marvin.utilities.openai.get_openai_client()
        if self.id is None:
            await self.create_async()

        content = content.append(formatted_image_files)
        response = await client.beta.threads.messages.create(
            thread_id=self.id, role=role, content=content, attachments=attachments
        )
        return response

    @expose_sync_method("add")
    async def add_async(
        self,
        message: str,
        role: str = "user",
        code_interpreter_files: Optional[list[str]] = None,
        file_search_files: Optional[list[str]] = None,
        image_files: Optional[list[str]] = None,
        file_search_attachments: List[Dict[str, Any]] = None,
        code_interpreter_attachments: List[Dict[str, Any]] = None,
        formatted_image_files: List[Dict[str, Any]] = None,
    ) -> Message:
        """
        Add a user message to the thread.

        You can also pass in pre-created attachments for code_interpreter and file_search tools.
        """
        client = marvin.utilities.openai.get_openai_client()

        if self.id is None:
            await self.create_async()

        content = [dict(text=message, type="text")]

        # Upload files and collect their IDs
        attachments = []
        for fp in code_interpreter_files or []:
            with open(fp, mode="rb") as file:
                response = await client.files.create(file=file, purpose="assistants")
                attachments.append(
                    dict(file_id=response.id, tools=[dict(type="code_interpreter")])
                )
        for fp in file_search_files or []:
            with open(fp, mode="rb") as file:
                response = await client.files.create(file=file, purpose="assistants")
                attachments.append(
                    dict(file_id=response.id, tools=[dict(type="file_search")])
                )
        for fp in image_files or []:
            with open(fp, mode="rb") as file:
                response = await client.files.create(file=file, purpose="vision")
                content.append(
                    dict(image_file=dict(file_id=response.id), type="image_file")
                )

        if formatted_image_files:
            content.append(formatted_image_files)

        if file_search_attachments:
            attachments.extend(file_search_attachments)

        if code_interpreter_attachments:
            attachments.extend(code_interpreter_attachments)

        # Create the message with the attached files
        response = await client.beta.threads.messages.create(
            thread_id=self.id, role=role, content=content, attachments=attachments
        )
        return response

    @expose_sync_method("add_messages")
    async def add_messages_async(
        self,
        messages: list[ChatMessage],
    ) -> list[Message]:
        """
        Add multiple messages to the thread, handling attachments, images, and file content.
        # TODO: THIS IS A WORK IN PROGRESS
        """
        marvin.utilities.openai.get_openai_client()
        # noqa
        raise NotImplementedError("This is a work in progress")

        # if self.id is None:
        #     await self.create_async()

        # added_messages = []

        # for message in messages:
        #     content = []
        #     attachments = []

        #     # Handle text content
        #     if isinstance(message.content, str):
        #         content.append({"type": "text", "text": message.content})
        #     elif isinstance(message.content, list):
        #         for item in message.content:
        #             if isinstance(item, TextContentBlock):
        #                 content.append({"type": "text", "text": item.text.value})

        #     # Handle attachments
        #     if message.metadata.attachments:
        #         for attachment in message.metadata.attachments:
        #             if isinstance(attachment, ImageMessageContent):
        #                 content.append(
        #                     {
        #                         "type": "image_url",
        #                         "image_url": {"url": attachment.metadata.url},
        #                     }
        #                 )
        #             elif isinstance(attachment, FileMessageContent):
        #                 with open(attachment.metadata.path, "rb") as file:
        #                     response = await client.files.create(
        #                         file=file, purpose="assistants"
        #                     )
        #                     attachments.append(
        #                         {
        #                             "file_id": response.id,
        #                             "tools": [{"type": "file_search"}],
        #                         }
        #                     )

        #     # Create the message with the attached files
        #     response = await client.beta.threads.messages.create(
        #         thread_id=self.id,
        #         role=message.role,
        #         content=content,
        #         attachments=attachments,
        #     )
        #     added_messages.append(response)

    @expose_sync_method("get_messages")
    async def get_messages_async(
        self,
        limit: int = None,
        before_message: Optional[str] = None,
        after_message: Optional[str] = None,
    ) -> list[Message]:
        """
        Asynchronously retrieves messages from the thread.

        Args:
            limit (int, optional): The maximum number of messages to return.
            before_message (str, optional): The ID of the message to start the
                list from, retrieving messages sent before this one.
            after_message (str, optional): The ID of the message to start the
                list from, retrieving messages sent after this one.
        Returns:
            list[Union[Message, dict]]: A list of messages from the thread
        """

        if self.id is None:
            await self.create_async()
        client = marvin.utilities.openai.get_openai_client()

        response = await client.beta.threads.messages.list(
            thread_id=self.id,
            # note that because messages are returned in descending order,
            # we reverse "before" and "after" to the API
            before=after_message,
            after=before_message,
            limit=limit,
            # order desc to get the most recent messages first
            order="desc",
        )
        return list(reversed(response.data))

    @expose_sync_method("delete")
    async def delete_async(self):
        client = marvin.utilities.openai.get_openai_client()
        await client.beta.threads.delete(thread_id=self.id)
        self.id = None

    @expose_sync_method("run")
    async def run_async(
        self,
        assistant: "Assistant",
        **run_kwargs,
    ) -> "Run":
        """
        Creates and returns a `Run` of this thread with the provided assistant.

        Args:
            assistant (Assistant): The assistant to run the thread with.
            run_kwargs: Additional keyword arguments to pass to the Run constructor.
        """
        if self.id is None:
            await self.create_async()

        from marvin.beta.assistants.runs import Run

        run = Run(
            assistant=assistant,
            thread=self,
            **run_kwargs,
        )
        return await run.run_async()

    @expose_sync_method("create_vector_store")
    async def create_vector_store_async(self, name: str) -> str:
        client = marvin.utilities.openai.get_openai_client()
        vector_store = await client.beta.vector_stores.create()
        self.vector_store_id = vector_store.id
        return vector_store

    @expose_sync_method("get_vector_store")
    async def get_vector_store_async(self) -> VectorStore:
        client = marvin.utilities.openai.get_openai_client()
        return await client.beta.vector_stores.retrieve(self.vector_store_id)

    @expose_sync_method("add_files_to_vector_store")
    async def add_files_to_vector_store_async(
        self, file_streams: List[ContentFile]
    ) -> None:
        vector_store_id = await self.get_vector_store_id_async()
        if not vector_store_id:
            vector_store = await self.create_vector_store_async()
            vector_store_id = vector_store.id

        client = marvin.utilities.openai.get_openai_client()
        # bulk open file streams

        file_streams = [(file.name, file.read()) for file in file_streams]
        response = await client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store_id, files=file_streams
        )

        return response

    @expose_sync_method("remove_file_from_vector_store")
    async def remove_file_from_vector_store_async(self, file_id: str) -> None:
        files = await self.get_vector_store_files_async()
        if file_id not in [file.id for file in files]:
            return

        client = marvin.utilities.openai.get_openai_client()
        await client.beta.vector_stores.files.delete(self.vector_store_id, file_id)

    @expose_sync_method("remove_vector_store")
    async def remove_vector_store_async(self) -> None:
        if not self.vector_store_id:
            return

        client = marvin.utilities.openai.get_openai_client()
        await client.beta.vector_stores.delete(self.vector_store_id)

    @expose_sync_method("has_vector_store")
    async def has_vector_store_async(self) -> bool:
        return await self.get_vector_store_id_async() is not None

    @expose_sync_method("get_vector_store_id")
    async def get_vector_store_id_async(self) -> str:
        client = marvin.utilities.openai.get_openai_client()
        thread = await client.beta.threads.retrieve(thread_id=self.id)
        return (
            thread.tool_resources.file_search.vector_store_ids[0]
            if thread.tool_resources.file_search
            else None
        )

    @expose_sync_method("get_vector_store_files")
    async def get_vector_store_files_async(self) -> List[VectorStoreFile]:
        client = marvin.utilities.openai.get_openai_client()
        vector_store_id = await self.get_vector_store_id_async()
        response = await client.beta.vector_stores.files.list(vector_store_id)
        return response.data

    @expose_sync_method("get_file_search_files")
    async def get_file_search_files_async(self) -> List[str]:
        # check if there is a vector store
        client = marvin.utilities.openai.get_openai_client()
        tool_resources = await client.beta.threads.retrieve(thread_id=self.id)
        vector_store_id = (
            tool_resources.tool_resources.file_search.vector_store_ids[0]
            if tool_resources.tool_resources.file_search
            else None
        )
        if not vector_store_id:
            return []
        files = await self.get_vector_store_files_async()
        return [file.id for file in files]

    @expose_sync_method("list_files")
    async def list_files_async(self) -> List[str]:
        client = marvin.utilities.openai.get_openai_client()
        thread = await client.beta.threads.retrieve(thread_id=self.id)
        code_interpreter_files = (
            thread.tool_resources.code_interpreter.file_ids
            if thread.tool_resources.code_interpreter
            else []
        )
        file_search_files = await self.get_file_search_files_async()
        return code_interpreter_files + file_search_files

    @expose_sync_method("update_files")
    async def update_files_async(
        self, add_files: List[str] = None, remove_files: List[str] = None
    ) -> None:
        if not self.vector_store_id:
            raise ValueError(
                "Vector store not created. Call create_vector_store first."
            )

        client = marvin.utilities.openai.get_openai_client()

        if add_files:
            file_streams = [open(path, "rb") for path in add_files]
            await client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=self.vector_store_id, files=file_streams
            )

        if remove_files:
            files = await client.beta.vector_stores.files.list(self.vector_store_id)
            for file in files.data:
                if file.filename in remove_files:
                    await client.beta.vector_stores.files.delete(
                        self.vector_store_id, file.id
                    )
