from typing import Any, Dict, List

import tiktoken


def get_encoding(model):
    # Attempt to get the encoding for the specified model
    if model is None:
        encoding = tiktoken.get_encoding("cl100k_base")
    else:
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")

    return encoding


def num_tokens_from_messages(messages: List[Dict[str, Any]], model) -> int:
    """
    Function to return the number of tokens used by a list of messages.
    """

    encoding = get_encoding(model)

    # Token handling specifics for different model types
    if model is None:
        # Slightly raised numbers for an unknown model / prompt template
        # In the future this should be customizable
        tokens_per_message = 4
        tokens_per_name = 2
    else:
        if model in {
            "gpt-3.5-turbo-0613",
            "gpt-3.5-turbo-16k-0613",
            "gpt-4-0314",
            "gpt-4-32k-0314",
            "gpt-4-0613",
            "gpt-4-32k-0613",
            "gpt-4o",
        }:
            tokens_per_message = 3
            tokens_per_name = 1
        elif model == "gpt-3.5-turbo-0301":
            tokens_per_message = 4
            tokens_per_name = -1
        elif "gpt-3.5-turbo" in model:
            return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
        elif "gpt-4" in model:
            return num_tokens_from_messages(messages, model="gpt-4-0613")
        else:
            # Slightly raised numbers for an unknown model / prompt template
            # In the future this should be customizable
            tokens_per_message = 4
            tokens_per_name = 2

    # Calculate the number of tokens
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            try:
                num_tokens += len(encoding.encode(str(value)))
                if key == "name":
                    num_tokens += tokens_per_name
            except Exception:
                pass

    num_tokens += 3
    return num_tokens


def number_of_tokens(string: str, model: str = None) -> int:
    """
    Function to return the number of tokens used by a string.
    """
    model = model or "gpt-4o"
    encoding = get_encoding(model)
    return len(encoding.encode(string))
