from io import BytesIO
from typing import Any


def encode_image(image_path):
    import base64

    with open(image_path, "rb") as image_file:
        return {
            "url": image_path,
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(image_file.read()).decode("utf-8"),
            },
        }


def encode_image_from_file(image_file: str | Any):
    """
    Also accepts django field file objects.
    """
    import base64

    if hasattr(image_file, "url"):
        url = image_file.url
    else:
        url = image_file

    return {
        "url": url,
        "source": {
            "type": "base64",
            "media_type": image_file.file.content_type,
            "data": base64.b64encode(image_file.read()).decode("utf-8"),
        },
    }


def encode_image_from_url(image_url):
    import base64

    import requests

    response = requests.get(image_url)
    return {
        "url": image_url,
        "source": {
            "data": base64.b64encode(response.content).decode("utf-8"),
            "media_type": response.headers["Content-Type"],
            "type": "base64",
        },
    }


def bulk_encode(
    image_paths: list[str] | list[BytesIO],
) -> list[str]:
    """
    Encode given images in bulk
    Runs in a multiprocessing pool to speed up the process
    """
    from multiprocessing import Pool

    encoder = (
        encode_image_from_file
        if isinstance(image_paths[0], BytesIO)
        else encode_image_from_url
    )

    with Pool() as pool:
        images = pool.map(encoder, image_paths)
        # map the images to their respective paths
        return images
