from typing import List
import litellm
from litellm import Usage, cost_per_token
from marvin.extensions.types.costs import ServiceCosts


def get_run_costs(model_response):
    """
    Run costs
    """
    try:
        prompt_cost_usd, completion_usd = cost_per_token(
            model_response.model,
            model_response.usage.prompt_tokens,
            model_response.usage.completion_tokens,
        )
    except litellm.exceptions.NotFoundError:
        model_response.model = "gpt-4-turbo"
        prompt_cost_usd, completion_usd = cost_per_token(
            model_response.model,
            model_response.usage.prompt_tokens,
            model_response.usage.completion_tokens,
        )
    except Exception:
        return {
            "id": model_response.id,
            "prompt_cost": 0,
            "completion_cost": 0,
            "total_cost": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    prompt_cost_usd_total = prompt_cost_usd * model_response.usage.prompt_tokens
    completion_usd_total = completion_usd * model_response.usage.completion_tokens

    return {
        "id": model_response.id,
        "prompt_cost": prompt_cost_usd_total,
        "completion_cost": completion_usd_total,
        "total_cost": prompt_cost_usd_total + completion_usd_total,
        "prompt_tokens": model_response.usage.prompt_tokens,
        "completion_tokens": model_response.usage.completion_tokens,
        "total_tokens": model_response.usage.total_tokens,
    }


def get_service_usage_costs(usage: Usage, model: str) -> ServiceCosts:
    """
    Calculate the service provider costs for a given usage
    """
    try:
        prompt_cost_usd, completion_usd = cost_per_token(
            model,
            usage.prompt_tokens,
            usage.completion_tokens,
        )
        return ServiceCosts(
            prompt_cost=prompt_cost_usd,
            completion_cost=completion_usd,
            total_cost=prompt_cost_usd + completion_usd,
        )
    except Exception:
        return ServiceCosts(
            prompt_cost=0,
            completion_cost=0,
            total_cost=0,
        )


def merge_run_costs(costs: List[dict]):
    """
    Sum up the run costs
    """

    return {
        "prompt_cost": sum(cost["prompt_cost"] for cost in costs),
        "completion_cost": sum(cost["completion_cost"] for cost in costs),
        "total_cost": sum(cost["total_cost"] for cost in costs),
        "prompt_tokens": sum(cost["prompt_tokens"] for cost in costs),
        "completion_tokens": sum(cost["completion_tokens"] for cost in costs),
        "total_tokens": sum(cost["total_tokens"] for cost in costs),
    }
