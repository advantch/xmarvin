from datetime import datetime
from typing import Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel
from marvin.extensions.types.base import BaseModelConfig
from openai.types.beta.threads.run import Run as OpenaiRun
from openai.types.beta.threads.runs import (
    RunStep,
    ToolCallsStepDetails,
    MessageCreationStepDetails,
)
from openai.types.beta.threads.runs.message_creation_step_details import MessageCreation
from .message import ChatMessage
from .events import StreamChatMessageEvent
from .costs import TokenCreditsUsage
from .tools import AnyToolCall


class RunMetadata(BaseModel):
    credits: TokenCreditsUsage | None = None
    events: list[StreamChatMessageEvent] | None = None
    messages: list[ChatMessage] | None = None
    message_ids: list[str] | None = None

    class Config(BaseModelConfig):
        extra = "allow"


class AppMessageCreationStepDetails(MessageCreationStepDetails):
    type: Literal["message_creation"] = "message_creation"
    message_creation: MessageCreation


class AppToolCallsStepDetails(ToolCallsStepDetails):
    tool_calls: list[AnyToolCall] | None = None
    type: Literal["tool_calls"] = "tool_calls"


class AppRunStep(RunStep):
    step_details: Union[AppMessageCreationStepDetails, AppToolCallsStepDetails]


class OpenaiRunSchema(OpenaiRun):
    class Config(BaseModelConfig):
        extra = "allow"

class PersistedRun(BaseModel):
    id: str | UUID | None = None
    thread_id: str | UUID | None = None
    tenant_id: str | UUID | None = None
    created: datetime | str | None = None
    modified: datetime | str | None = None
    run: OpenaiRunSchema | None = None
    steps: list[AppRunStep] | None = []
    metadata: dict | RunMetadata | None = RunMetadata()
    data: dict | None = None
    status: Any | None = None

    class Config(BaseModelConfig):
        extra = "allow"


    def save_run_context_data(self, context: dict):
        """
        Update the run with the data from the context.
        Existing data will be overwritten.
        """
        storage = context.get("storage", {})
        run_metadata = storage.get("run_metadata", {})
        openai_run = run_metadata.get('run', None)
        metadata = openai_run.get("metadata", {})
        if openai_run:
            self.run = OpenaiRunSchema.model_validate(openai_run)
        steps = run_metadata.get("steps", [])
        self.steps = steps
        self.metadata = RunMetadata.model_validate(metadata)

        return self