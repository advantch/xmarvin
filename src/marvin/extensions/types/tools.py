from typing import Any, Dict, Union

from openai._utils import PropertyInfo
from openai.types.beta.threads.runs import (
    CodeInterpreterToolCall as OpenAICodeInterpreterToolCall,
)
from openai.types.beta.threads.runs import (
    FileSearchToolCall as OpenAIFileSearchToolCall,
)
from openai.types.beta.threads.runs.function_tool_call import (
    Function as OpenAIFunction,
)
from openai.types.beta.threads.runs.function_tool_call import (
    FunctionToolCall as OpenAIFunctionToolCall,
)
from pydantic import BaseModel, Field
from typing_extensions import Annotated, TypeAlias


class ToolResponse(BaseModel):
    tool: str
    response: Any
    response_required: bool
    tool_call_id: str | None = None
    raw_response: Any | None = None


class ToolCall(BaseModel):
    arguments: Dict[str, Any] | None
    id: str | None
    name: str | None

    class Config:
        extra = "allow"


class ToolSelection(BaseModel):
    """Tool selection."""

    tool_id: str = Field(description="Tool ID to select.")
    tool_name: str = Field(description="Tool name to select.")
    tool_kwargs: Dict[str, Any] = Field(description="Keyword arguments for the tool.")


class AppFunction(OpenAIFunction):
    """Function with structured output."""

    structured_output: Any | None = Field(
        description="Structured output of the tool.", default=None
    )


class AppCodeInterpreterTool(OpenAICodeInterpreterToolCall):
    """Code interpreter tool with structured output."""

    structured_output: Any | None = Field(
        description="Structured output of the tool.", default=None
    )

    @classmethod
    def dump(cls, tool: OpenAICodeInterpreterToolCall):
        c = [c.model_dump() for c in tool.code_interpreter.outputs]
        return {
            "type": "code_interpreter",
            "code_interpreter": {
                "input": tool.code_interpreter.input,
                "outputs": c,
            },
            "structured_output": c,
        }


class AppFileSearchTool(OpenAIFileSearchToolCall):
    """File search tool with structured output."""

    structured_output: Any | None = Field(
        description="Structured output of the tool.", default=None
    )


class AppToolCall(OpenAIFunctionToolCall):
    """Structured tool call."""

    function: AppFunction


AnyToolCall: TypeAlias = Annotated[
    Union[AppToolCall, AppCodeInterpreterTool, AppFileSearchTool],
    PropertyInfo(discriminator="type"),
]
