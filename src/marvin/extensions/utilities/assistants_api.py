import os
import tempfile
from typing import IO

from openai import AsyncOpenAI, OpenAI
from openai.types import FileObject

from marvin.settings import settings


def get_client(api_key=None):
    api_key = api_key or settings.openai.api_key
    assert settings.openai.api_key == api_key

    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_async_client(api_key=None):
    api_key = api_key or settings.openai.api_key
    return AsyncOpenAI(api_key=api_key)


def upload_assistants_file(file: IO, name: str, purpose="assistants") -> FileObject:
    """
    Upload a file to OpenAI
    """
    client = get_client()
    byte_content = file.read()
    # Ensure the name is only the file name, not a full path
    _, file_extension = os.path.splitext(name)
    temp_suffix = file_extension or ".tmp"

    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=temp_suffix) as temp_file:
        temp_file.write(byte_content)
        temp_filename = temp_file.name

    try:
        # Open the temporary file and send it to OpenAI
        with open(temp_filename, "rb") as temp_file:
            data = client.files.create(file=temp_file, purpose=purpose)
    finally:
        # Ensure the temporary file is deleted after use
        os.remove(temp_filename)

    file.close()
    return data


def create_thread_message(
    thread_id,
    content,
    attachments=None,
):
    client = get_client()
    file_attachments = {}
    if attachments:
        file_attachments = {"attachments": attachments}
    return client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=content,
        **file_attachments,
    )


def download_assistants_file_info(file_id):
    client = get_client()
    return client.files.retrieve(file_id)


def download_assistants_file_content(file_id):
    client = get_client()
    return client.files.content(file_id)


def cancel_thread_run(thread_id, run_id):
    client = get_client()
    return client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)


async def cancel_thread_run_async(thread_id, run_id):
    client = get_async_client()
    return await client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
