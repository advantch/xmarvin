import mimetypes
import os

import magic
from magika import Magika
from marvin.extensions.utilities.logging import logger


def get_magic_mimetype(file_bytes: bytes):
    magika = Magika()
    try:
        file_type = magika.identify_bytes(file_bytes)
        mime_type = file_type.output.mime_type

        if mime_type == "inode/x-empty":
            raise Exception("File is empty")
        return mime_type
    except Exception:
        return None


def get_mime_type(file_bytes, file_name=None):
    """
    Guess the MIME type of a file based on its filename or content.

    Args:
        file_path (str): The path to the file.

    Returns:
        str: The MIME type of the file.
    """

    mime_type = get_magic_mimetype(file_bytes)
    if mime_type is not None:
        return mime_type
    # If the MIME type couldn't be guessed based on the file extension, use python-magic
    try:
        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(file_bytes)

        return mime_type
    except Exception:
        # use extension
        if file_name is not None:
            try:
                os.path.splitext(file_name)[1]
                mime_type = mimetypes.guess_type(file_name)[0]
            except Exception as e:
                logger.error(f"Error guessing MIME type from file extension: {e}")
                return None
            return None
    return mime_type
