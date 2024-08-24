import tiktoken
from apps.common.logging import logger
from apps.payments.models import UsageRecord


class Services:
    openai = "openai"
    cohere = "cohere"
    gpt35 = "gpt35"
    gpt4 = "gpt4"


def record_usage(output, service, channel_id, asy=False, actions=None):
    """Record usage for a given service"""

    actions = actions or []
    try:
        logger.debug(f"record_usage channel_id {str(channel_id)}")

    except Exception as e:
        logger.error(f"!!!$\n generate-text:Record usage: chat history error {e}")
        raise e

    try:
        # calculate tokens
        if output.get("token_count"):
            tokens = output["token_count"]
        else:
            # if service == Services.openai:
            tokens = output["llm_output"]["token_usage"]["total_tokens"]
        # input tokens
        # from last chat message by user?

        total_credits = tokens * 0.75
        # update usage record
        UsageRecord.objects.record_usage(
            quantity=total_credits, service=service, tokens=tokens
        )
        for generation_id, actions_items in actions.items():
            logger.debug(f"record_usage generation_id {str(generation_id)}")
            # TODO actions

    except Exception as e:
        logger.error(f"generate-text:Record usage: token error {e}")

    try:
        # record the api response data
        obj = UsageRecord.objects.create(
            service=service,
            metadata=output,
        )
        return obj

    except Exception as e:
        logger.error(f"generate-text:Create response: response error {e}")
        return None


def record_usage_simple(output, service):
    """Record usage for a given service"""

    try:
        # calculate tokens
        if output.get("token_count"):
            tokens = output["token_count"]
        else:
            # if service == Services.openai:
            tokens = output["llm_output"]["token_usage"]["total_tokens"]
        # input tokens

        total_credits = tokens * 0.75

        # update usage record
        UsageRecord.objects.record_usage(
            quantity=total_credits, service=service, tokens=tokens
        )

    except Exception as e:
        logger.error(f"generate-text:Record usage: token error {e}")
        pass

    try:
        # record the api response data
        obj = UsageRecord.objects.create(
            service=service,
            metadata=output,
        )
        return obj

    except Exception as e:
        logger.error(f"generate-text:Create response: response error {e}")
        return None


def num_tokens_from_string(string: str, encoding_name: str = "cl100k_base") -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


def token_count(string, model_name=None, action="count", max_value=400):
    model_name = model_name or "gpt-3.5-turbo"

    def _count_string(string_val):
        try:
            return len(string_val.split(" ")) * 0.75
        except Exception:
            return None

    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        return _count_string(string)

    try:
        tokens = encoding.encode(string)
        if action == "count":
            return len(tokens)
        if action == "truncate":
            tokens = tokens[:max_value]
            return encoding.decode(tokens)
    except Exception:
        return len(string.split(" ")) * 0.75
