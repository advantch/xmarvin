from datetime import datetime
from typing import Any, Literal, Union
from uuid import UUID
from typing import List
from marvin.extensions.types.base import BaseModelConfig
from openai.types.beta.threads.run import Run as OpenaiRun
from openai.types.beta.threads.runs import (
    MessageCreationStepDetails,
    RunStep,
    ToolCallsStepDetails,
)
from openai.types.beta.threads.runs.message_creation_step_details import MessageCreation
from pydantic import BaseModel

from .costs import TokenCreditsUsage
from .events import StreamChatMessageEvent
from .message import ChatMessage
from .tools import AnyToolCall


class RunMetadata(BaseModel):
    credits: TokenCreditsUsage | None = None
    events: List[StreamChatMessageEvent] | None = None
    messages: List[ChatMessage] | None = None
    message_ids: List[str] | None = None

    class Config(BaseModelConfig):
        extra = "allow"


class AppMessageCreationStepDetails(MessageCreationStepDetails):
    type: Literal["message_creation"] = "message_creation"
    message_creation: MessageCreation


class AppToolCallsStepDetails(ToolCallsStepDetails):
    tool_calls: List[AnyToolCall] | None = None
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
    steps: List[AppRunStep] | None = []
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

        # save run and metadata if run was created
        openai_run = run_metadata.get("run", None)

        if openai_run:
            metadata = openai_run.get("metadata", {})
            openai_run['tools'] = openai_run.get("tools", None) or []
            self.run = OpenaiRunSchema.model_validate(openai_run)
            self.metadata = RunMetadata.model_validate(metadata)

        steps = run_metadata.get("steps", [])
        self.steps = steps

        return self
