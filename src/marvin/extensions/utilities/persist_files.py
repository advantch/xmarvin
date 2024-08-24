from marvin.extensions.tools.function_tool import sync_to_async
from marvin.extensions.types import ChatMessage
from marvin.extensions.utilities.context import RunContext
from marvin.extensions.utilities.unique_id import generate_uuid_from_string
from openai.types.beta.threads import ImageFile


async def save_assistant_image_to_storage(
    context: RunContext, image_file: ImageFile
) -> None:
    """
    Saves OPENAI Assistant image file to db
    """

    from apps.ai.models import Message as ChatMessageModel
    from apps.ai.models.dataset import DataSource

    # fetch the image file here
    result: dict = await DataSource.objects.aadd_file_from_code_interpreter(
        image_file,
        thread_id=context.thread_id,
        run_id=context.run_id,
        tenant_id=context.tenant_id,
    )

    # create a chat message
    m = ChatMessage(
        id=generate_uuid_from_string(image_file.file_id),
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

    # save to db
    await sync_to_async(ChatMessageModel.objects.create_or_update)(
        data=m.model_dump(),
        thread_id=context.thread_id,
        run_id=context.run_id,
        tenant_id=context.tenant_id,
    )

    return m
