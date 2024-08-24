from typing import Literal

from pydantic import BaseModel


class ServiceCosts(BaseModel):
    prompt_cost: float
    completion_cost: float
    total_cost: float


class TokenCreditsUsage(BaseModel):
    cost: float
    per_token: float
    tokens: int
    model: str
    type: Literal["generation", "embedding"] = "generation"
    provider: Literal[
        "openai", "anthropic", "cohere", "google", "bedrock", "groq"
    ] = "openai"
    service_costs: dict | None = None
