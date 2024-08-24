from typing import BinaryIO

from marvin.extensions.storage.base import BaseFileStorage
from marvin.extensions.types import ChatMessage
from marvin.extensions.utilities.context import RunContext
from marvin.extensions.utilities.unique_id import generate_uuid_from_string


async def save_assistant_image_to_storage(
    context: RunContext, image_file: BinaryIO, file_storage: BaseFileStorage
) -> None:
    """
    Saves assistant image file to storage
    """
    file_id = generate_uuid_from_string(str(context.run_id))

    # Save the image file
    result: dict = await file_storage.save_file(
        image_file,
        file_id,
        metadata={
            "thread_id": context.thread_id,
            "run_id": context.run_id,
            "tenant_id": context.tenant_id,
        },
    )

    # Create a chat message
    m = ChatMessage(
        id=file_id,
        role="assistant",
        content=[result],
        run_id=context.run_id,
        thread_id=context.thread_id,
        metadata={
            "streaming": False,
            "type": "image",
            "run_id": context.run_id,
        },
    )

    return m
