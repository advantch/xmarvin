from pathlib import Path

from marvin.extensions.utilities.file_parse import get_mime_type


def test_mime_type():
    # create a txt file
    local_path = Path(__file__).parent / "test_file_upload.py"
    with open(local_path, "rb") as f:
        file_bytes = f.read()
    mime_type = get_mime_type(file_bytes)
    assert mime_type == "text/x-python"
