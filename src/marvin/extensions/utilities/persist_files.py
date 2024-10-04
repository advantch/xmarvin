from openai.types.beta.threads import ImageFile

from marvin.extensions.context.run_context import get_current_run
from marvin.extensions.file_storage.base import BaseBlobStorage
from marvin.extensions.types.data_source import DataSource, ExternalFileReference
from marvin.extensions.utilities.assistants_api import download_assistants_file_content
from marvin.extensions.utilities.file_utilities import ContentFile
from marvin.extensions.utilities.unique_id import generate_id


async def save_assistant_image_to_storage(
    image_file: ImageFile,
    file_storage: BaseBlobStorage | None = None,
    identifier: str | None = None,
) -> DataSource:
    """
    Saves assistant image file to storage
    Include a data source reference to store the image file reference
    """
    data_source_id = generate_id("ds", str(image_file.file_id))
    file_content = download_assistants_file_content(image_file.file_id)

    content_file = ContentFile(file_content.content, name=str(image_file.file_id))
    mime_type = content_file.content_type
    name = data_source_id

    if mime_type is not None:
        name = f"{data_source_id}.{mime_type.split('/')[1]}"

    data_source = DataSource(
        id=data_source_id,
        name=str(name),
        file_type="image",
        reference={
            "file_id": image_file.file_id,
            "detail": image_file.detail,
        },
    )

    ctx = get_current_run()
    data_source_store = ctx.stores.data_source_store
    file_storage = ctx.stores.file_storage

    file_metadata = await file_storage.save_file_async(content_file, data_source_id)

    # save the data source
    data_source.metadata = file_metadata
    data_source.upload_type = "image"
    data_source.file_store_metadata = file_metadata
    data_source.external_file_reference = ExternalFileReference.model_validate(
        image_file.model_dump()
    )
    data_source.external_file_reference.purpose = "code_interpreter"
    data_source.external_file_reference.type = "file_reference"
    data_source = await data_source_store.save_data_source_async(data_source)

    return data_source
