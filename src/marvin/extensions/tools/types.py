import json
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass


@dataclass
class ToolMetadata:
    description: str
    name: Optional[str] = None
    fn_schema: Optional[Type[BaseModel]] | str | None = None
    human_description: Optional[str] = None
    title: Optional[str] = None
    tool_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None  # reserved for future use
    is_live: bool | None = None
    return_direct: bool | None = None
    spec_name: Optional[str] = None
    tool_hash: Optional[str] = Field(
        default=None, description="Unique Hash of the tool"
    )
    variables: Optional[List[str | dict] | dict] = Field(
        default={}, description="Variables to be used in the tool"
    )
    required_variables: Optional[List[dict]] = Field(
        default=[], description="Required variables to be used in the tool"
    )

    @property
    def _tool_id(self) -> str:
        return self.tool_id or self.name

    def get_parameters_dict(self) -> dict:
        if self.fn_schema is None:
            parameters = {
                "type": "object",
                "properties": {
                    "input": {"title": "input query string", "type": "string"},
                },
                "required": ["input"],
            }
        else:
            parameters = self.fn_schema.schema()
            parameters = {
                k: v
                for k, v in parameters.items()
                if k in ["type", "properties", "required", "definitions"]
            }
        return parameters

    @property
    def fn_schema_str(self) -> str:
        """Get fn schema as string."""
        if self.fn_schema is None:
            raise ValueError("fn_schema is None.")
        parameters = self.get_parameters_dict()
        return json.dumps(parameters)

    def get_name(self) -> str:
        """Get name."""
        if self.name is None:
            raise ValueError("name is None.")
        return self.name

    def to_openai_tool(self) -> Dict[str, Any]:
        """To OpenAI tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters_dict(),
            },
        }


class ToolOutput(BaseModel):
    """Tool output."""

    content: str
    tool_name: str
    raw_input: Dict[str, Any]
    raw_output: Any
    tool_call_id: str | None = None
    metadata: ToolMetadata | None = None

    def __str__(self) -> str:
        """String."""
        return str(self.content)


class BaseTool:
    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        pass

    @abstractmethod
    def __call__(self, input: Any) -> ToolOutput:
        pass


class AsyncBaseTool(BaseTool):
    """
    Base-level tool class that is backwards compatible with the old tool spec but also
    supports async.
    """

    def __call__(self, *args: Any, **kwargs: Any) -> ToolOutput:
        return self.call(*args, **kwargs)

    @abstractmethod
    def call(self, input: Any) -> ToolOutput:
        """
        This is the method that should be implemented by the tool developer.
        """

    @abstractmethod
    async def acall(self, input: Any) -> ToolOutput:
        """
        This is the async version of the call method.
        Should also be implemented by the tool developer as an
        async-compatible implementation.
        """


class BaseToolAsyncAdapter(AsyncBaseTool):
    """
    Adapter class that allows a synchronous tool to be used as an async tool.
    """

    def __init__(self, tool: BaseTool):
        self.base_tool = tool

    @property
    def metadata(self) -> ToolMetadata:
        return self.base_tool.metadata

    def call(self, input: Any) -> ToolOutput:
        return self.base_tool(input)

    async def acall(self, input: Any) -> ToolOutput:
        return self.call(input)


class SpecDefinition(BaseModel):
    """Spec Definition."""

    name: str
    description: str
    context_variables: List[str | dict]
