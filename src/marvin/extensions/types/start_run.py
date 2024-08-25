from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from .agent import AgentConfig, RuntimeConfig
from .message import ChatMessage


class TriggerAgentRun(BaseModel):
    """
    Body for starting a run.
    This is passed to the thread runner to start a run.
    """

    message: ChatMessage
    run_id: UUID
    tenant_id: str | UUID | None = None
    channel_id: str | UUID | None = None
    thread_id: str | UUID | None = None
    agent_id: str | UUID | None = None
    user_id: str | int | UUID | None = None
    tags: list[str] | None = ["chat"]
    runtime_config: RuntimeConfig | None = None
    agent_config: AgentConfig | None = None
    preset: Literal["default", "admin"] | None = Field(
        default=None,
        description="This will override the agent_config and use the preset agent.",
    )
