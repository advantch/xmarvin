import hashlib
import random
import time
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


def generate_sf_like_id(prefix: str) -> str:
    """
    Generates a unique ID similar to Snowflake IDs.
    Usage:
    thread ids = generate_sf_like_id("th")  -> th_12345678901234567890
    chat ids = generate_sf_like_id("ct")  -> ct_12345678901234567890
    vector store ids = generate_sf_like_id("vs")  -> vs_12345678901234567890
    data source ids = generate_sf_like_id("ds")  -> ds_12345678901234567890
    """
    timestamp = int(time.time() * 1000)  # Current time in milliseconds
    random_bits = random.getrandbits(20)  # Random number for uniqueness
    return f"{prefix}_{timestamp}{random_bits}"


def generate_id(
    prefix: str, unique_id: str = None, seed: str = None, length: int = 16
) -> str:
    """
    Generates a unique ID with a prefix.
    Usage:
    file ids = generate_id("fs")
    thread ids = generate_id("th")
    chat ids = generate_id("ct")
    vector store ids = generate_id("vs")
    data source ids = generate_id("ds")
    """

    unique_id = unique_id or uuid.uuid4().hex[:length]
    return generate_uuid_from_string(str(unique_id))
    # if seed:
    #     unique_id = generate_uuid_from_string(str(unique_id))[:length]
    # timestamp = int(time.time() * 1000)  # order by time
    # return f"{timestamp}-{prefix}{unique_id}"
