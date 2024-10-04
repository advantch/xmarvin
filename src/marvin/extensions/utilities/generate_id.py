import random
import time
import uuid


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


def generate_id(prefix: str, length: int = 8) -> str:
    """
    Generates a unique ID with a prefix.
    Usage:
    file ids = generate_id("fs")
    thread ids = generate_id("th")
    chat ids = generate_id("ct")
    vector store ids = generate_id("vs")
    data source ids = generate_id("ds")
    """
    unique_id = uuid.uuid4().hex[:length]
    timestamp = int(time.time() * 1000)  # Current time in milliseconds
    return f"{prefix}_{timestamp}{unique_id}"
