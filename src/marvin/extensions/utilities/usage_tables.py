from enum import Enum
from functools import lru_cache
from typing import Any, Dict

from apps.common.logging import logger

from marvin.extensions.types.costs import TokenCreditsUsage
from marvin.extensions.utilities.cost_calculator import get_service_usage_costs


class AIModels(Enum):
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4O = "gpt-4o"
    CLAUDE_3_OPUS = "claude-3-opus"
    CLAUDE_3_HAIKU = "claude-3-haiku"
    CLAUDE_3_5_SONNET = "claude-3.5-sonnet"
    CLAUDE_3_SONNET = "claude-3-sonnet"
    COMMAND_PLUS = "command-plus"
    COMMAND_PLUS_R = "command-plus-r"
    GEMINI_FLASH = "gemini-flash"


USAGE_TABLE: Dict[str, Dict[str, Dict[str, float]]] = {
    "model": {
        "default": {
            "cost": 0.00001,
            "token": 1,
            "original_cost": 0.000001,
        },
        AIModels.GPT_4O_MINI.value: {
            "cost": 0.00001,
            "token": 1,
            "original_cost": 0.000002,
        },
        AIModels.GPT_4O.value: {
            "cost": 0.001,
            "token": 1,
            "original_cost": 0.00003,
        },
        AIModels.CLAUDE_3_OPUS.value: {
            "cost": 0.001,
            "token": 1,
            "original_cost": 0.00004,
        },
        AIModels.CLAUDE_3_HAIKU.value: {
            "cost": 0.00001,
            "token": 1,
            "original_cost": 0.000001,
        },
        AIModels.CLAUDE_3_5_SONNET.value: {
            "cost": 0.001,
            "token": 1,
            "original_cost": 0.00004,
        },
        AIModels.CLAUDE_3_SONNET.value: {
            "cost": 0.0001,
            "token": 1,
            "original_cost": 0.0001,
        },
        AIModels.COMMAND_PLUS.value: {
            "cost": 0.00001,
            "token": 1,
            "original_cost": 0.000001,
        },
        AIModels.COMMAND_PLUS_R.value: {
            "cost": 0.00001,
            "token": 1,
            "original_cost": 0.000001,
        },
        AIModels.GEMINI_FLASH.value: {
            "cost": 0.00001,
            "token": 1,
            "original_cost": 0.000001,
        },
    },
    "embeddings": {
        "default": {
            "cost": 0.000001,
            "token": 1,
            "original_cost": 0.000001,
        }
    },
    "enrichment": {
        "default": {
            "cost": 0.000001,
            "token": 1,
            "original_cost": 0.000001,
        }
    },
}


class ModelServiceNotFoundError(Exception):
    pass


def service_from_model(model: str) -> str:
    service_mapping = {
        "openai": [AIModels.GPT_4O_MINI.value, AIModels.GPT_4O.value],
        "anthropic": [
            AIModels.CLAUDE_3_OPUS.value,
            AIModels.CLAUDE_3_HAIKU.value,
            AIModels.CLAUDE_3_SONNET.value,
            AIModels.CLAUDE_3_5_SONNET.value,
        ],
        "cohere": [AIModels.COMMAND_PLUS.value, AIModels.COMMAND_PLUS_R.value],
        "google": [AIModels.GEMINI_FLASH.value],
    }

    for service, models in service_mapping.items():
        if model in models:
            return service

    raise ModelServiceNotFoundError(
        f"Model service cost: {model} not found. Add model to ai/core/utilities/usage_tables.py"
    )


@lru_cache(maxsize=128)
def get_model_cost(model: str) -> float:
    return USAGE_TABLE["model"].get(model, USAGE_TABLE["model"]["default"])["cost"]


def calculate_credits(run: Any, default_markup: float = 1.5) -> TokenCreditsUsage:
    tokens = run.usage.total_tokens
    model = run.model

    cost = get_model_cost(model)
    credits_total = cost * tokens * default_markup

    def _per_token_cost(credits: float, token: int) -> float:
        return credits / token if token != 0 else 0

    try:
        provider = service_from_model(model)
    except ModelServiceNotFoundError as e:
        logger.error(str(e))
        provider = "openai"

    return TokenCreditsUsage(
        cost=credits_total,
        per_token=_per_token_cost(credits_total, tokens),
        tokens=tokens,
        model=model,
        type="generation",
        service_costs=get_service_usage_costs(run.usage, model),
        provider=provider,
    )
