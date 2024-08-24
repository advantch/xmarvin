import hashlib
import uuid


def generate_uuid_from_string(input_string: str, as_string=False):
    """Convert a string to a UUID."""
    sha1 = hashlib.sha1()
    try:
        sha1.update(input_string.encode("utf-8"))
    except AttributeError:
        sha1.update(str(input_string).encode("utf-8"))

    uid = uuid.UUID(sha1.hexdigest()[:32])
    if as_string:
        return str(uid)
    return uid
