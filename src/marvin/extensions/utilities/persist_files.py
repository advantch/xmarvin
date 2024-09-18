from typing import BinaryIO

from marvin.extensions.context.run_context import RunContext
from marvin.extensions.storage.file_storage.local_file_storage import BaseFileStorage
from marvin.extensions.types import ChatMessage
from marvin.extensions.utilities.unique_id import generate_uuid_from_string


async def save_assistant_image_to_storage(
    context: RunContext, image_file: BinaryIO, file_storage: BaseFileStorage
) -> None:
    """
    Saves assistant image file to storage
    """
    file_id = generate_uuid_from_string(str(context.run_id))

    # Save the image file
    result: dict = await file_storage.save_file_async(
        image_file,
        file_id,
        metadata={
            "thread_id": context.thread_id,
            "run_id": context.run_id,
            "tenant_id": context.tenant_id,
        },
    )
    metadata = {
        "thread_id": context.thread_id,
        "run_id": context.run_id,
        "tenant_id": context.tenant_id,
        "type": "image",
    }
    from marvin.extensions.settings import extension_settings
    data_source_store = extension_settings.storage.data_source_storage_class()
    return await data_source_store.save_file_async(image_file, metadata)