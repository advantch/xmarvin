from typing import Any

from marvin.extensions.types.costs import TokenCreditsUsage
from marvin.extensions.types.llms import AIModels
from marvin.extensions.utilities.cost_calculator import get_service_usage_costs


class ModelServiceNotFoundError(Exception):
    pass


def calculate_credits(
    run: Any,
) -> TokenCreditsUsage:
    tokens = run.usage.total_tokens
    model = run.model

    service_costs = get_service_usage_costs(run.usage, model)

    def _per_token_cost(tokens: int) -> float:
        return service_costs["total_cost"] / tokens if tokens != 0 else 0

    return TokenCreditsUsage(
        cost=service_costs["total_cost"],
        per_token=_per_token_cost(tokens),
        tokens=tokens,
        model=model,
        type="generation",
        service_costs=service_costs,
        provider=AIModels.provider(model),
    )
