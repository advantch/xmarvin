import functools
import inspect
import json
import logging
import traceback
import typing
import uuid
from typing import Annotated, Any, Callable, Dict, Optional, Union

import langchain_core.tools
import pydantic
import pydantic.v1
from langchain_core.messages import InvalidToolCall, ToolCall
from litellm import ChatCompletionMessageToolCall
from marvin.utilities.tools import Function, ModelSchemaGenerator
from prefect.utilities.asyncutils import run_coro_as_sync
from pydantic import (
    BaseModel,
    Field,
    PydanticSchemaGenerationError,
    TypeAdapter,
    model_validator,
)

from ...agent.monitoring.logging import pretty_log

logger = logging.getLogger(__name__)


class Tool(BaseModel):
    name: str = Field(description="The name of the tool")
    description: str = Field(
        description="A description of the tool, which is provided to the LLM"
    )
    custom_name: Optional[str] = Field(
        None, description="An optional custom name to use for the tool"
    )
    custom_description: Optional[str] = Field(
        None, description="An optional custom description to use for the tool"
    )
    instructions: Optional[str] = Field(
        None,
        description="Optional instructions to display to the agent as part of the system prompt"
        " when this tool is available. Tool descriptions have a 1024 "
        "character limit, so this is a way to provide extra detail about behavior.",
    )
    parameters: dict = Field(
        description="The JSON schema for the tool's input parameters"
    )
    metadata: dict = {}
    config: dict | None = Field(
        None,
        description="The configuration for the tool",
    )
    settings: dict = {}
    private: bool = False
    end_turn: bool = Field(
        False,
        description="If True, using this tool will end the agent's turn instead "
        "of showing the result to the agent.",
    )

    fn: Callable = Field(
        None,
        exclude=True,
    )

    db_id: Optional[str | uuid.UUID] = Field(
        None, description="The id of the database to use for this tool"
    )
    settings: dict = {}

    def to_lc_tool(self) -> dict:
        payload = self.model_dump(include={"name", "description", "parameters"})
        return dict(type="function", function=payload)

    def run(self, input: dict):
        result = self.fn(**input)
        if inspect.isawaitable(result):
            result = run_coro_as_sync(result)

        # prepare artifact
        passed_args = inspect.signature(self.fn).bind(**input).arguments
        try:
            # try to pretty print the args
            passed_args = json.dumps(passed_args, indent=2)
        except Exception:
            pass

        return result

    async def run_async(self, input: dict):
        result = self.fn(**input)
        if inspect.isawaitable(result):
            result = await result

        # prepare artifact
        passed_args = inspect.signature(self.fn).bind(**input).arguments
        try:
            # try to pretty print the args
            passed_args = json.dumps(passed_args, indent=2)
        except Exception:
            pass
        return result

    @classmethod
    def from_function(
        cls,
        fn: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        instructions: Optional[str] = None,
        include_param_descriptions: bool = True,
        include_return_description: bool = True,
        **kwargs,
    ):
        name = name or fn.__name__
        description = description or fn.__doc__ or ""
        kwargs["custom_name"] = name or kwargs.get("custom_name", None)
        kwargs["custom_description"] = description or kwargs.get(
            "custom_description", None
        )
        config = kwargs.pop("config", None)
        signature = inspect.signature(fn)
        try:
            parameters = TypeAdapter(fn).json_schema()
        except PydanticSchemaGenerationError as e:
            logger.error(f'Could not generate a schema for tool "{name}". {e}')
            raise ValueError(
                f'Could not generate a schema for tool "{name}". '
                "Tool functions must have type hints that are compatible with Pydantic."
            )

        # load parameter descriptions
        if include_param_descriptions:
            for param in signature.parameters.values():
                # handle Annotated type hints
                if typing.get_origin(param.annotation) is Annotated:
                    param_description = " ".join(
                        str(a) for a in typing.get_args(param.annotation)[1:]
                    )
                # handle pydantic Field descriptions
                elif param.default is not inspect.Parameter.empty and isinstance(
                    param.default, pydantic.fields.FieldInfo
                ):
                    param_description = param.default.description
                else:
                    param_description = None

                if param_description:
                    parameters["properties"][param.name][
                        "description"
                    ] = param_description

        # Handle return type description

        if (
            include_return_description
            and signature.return_annotation is not inspect._empty
        ):
            return_schema = {}
            try:
                return_schema.update(
                    TypeAdapter(signature.return_annotation).json_schema()
                )
            except PydanticSchemaGenerationError:
                pass
            finally:
                if typing.get_origin(signature.return_annotation) is Annotated:
                    return_schema["annotation"] = " ".join(
                        str(a) for a in typing.get_args(signature.return_annotation)[1:]
                    )

            if return_schema:
                description += f"\n\nReturn value schema: {return_schema}"

        if not description:
            description = "(No description provided)"

        if len(description) > 1024:
            raise ValueError(
                inspect.cleandoc(
                    f"""
                {name}: The tool's description exceeds 1024
                characters. Please provide a shorter description, fewer
                annotations, or pass
                `include_param_descriptions=False` or
                `include_return_description=False` to `from_function`.
                """
                ).replace("\n", " ")
            )

        tool = cls(
            name=name,
            description=description,
            parameters=parameters,
            fn=fn,
            instructions=instructions,
            **kwargs,
        )

        if config and not isinstance(config, dict):
            try:
                tool.settings = config.model_json_schema(
                    schema_generator=ModelSchemaGenerator
                )

            except Exception:
                traceback.print_exc()
                pass

        # if is BaseModel class then just
        tool.config = config if isinstance(config, dict) else {}

        return tool

    @classmethod
    def from_lc_tool(cls, tool: langchain_core.tools.BaseTool, **kwargs):
        fn = tool._run
        return cls(
            name=tool.name,
            description=tool.description,
            parameters=tool.args_schema.schema(),
            fn=fn,
            **kwargs,
        )

    def serialize_for_prompt(self) -> dict:
        return self.model_dump(include={"name", "description"})

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": Function(
                name=self.name,
                description=self.description,
                parameters=self.parameters,
            ).model_dump(),
        }

    def function_tool(self) -> dict:
        from marvin.types import Function as MarvinFunction
        from marvin.types import FunctionTool

        return FunctionTool(
            type="function",
            function=MarvinFunction.create(
                name=self.name,
                description=self.description,
                parameters=self.parameters,
                _python_fn=self.fn,
            ),
        )


class ApiTool(Tool):
    """
    Expose in API.
    Removes fn as can not be serialized by ninja
    """

    fn: None | dict = None
    tool_id: str | None = None

    @model_validator(mode="after")
    def unset_fn(self):
        self.fn = None
        return self

    @classmethod
    def from_tool(cls, tool: Tool):
        dict_tool = tool.model_dump()
        dict_tool["fn"] = None
        return cls(**dict_tool)

    @classmethod
    def as_tool(cls, tool: Tool):
        from marvin.extensions.tools.app_tools import get_tool_by_name

        fn = get_tool_by_name(tool.name)
        tool.fn = fn
        return tool


class ToolConfig(BaseModel):
    tool: Tool
    config: Optional[Dict[str, Any]] = None

    class Config:
        arbitrary_types_allowed = True


def tool(
    fn: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    instructions: Optional[str] = None,
    include_param_descriptions: bool = True,
    include_return_description: bool = True,
    metadata: Optional[dict] = {},
    config: Optional[BaseModel | dict] = {},
    **kwargs,
) -> Tool:
    """
    Decorator for turning a function into a Tool
    """
    kwargs.update(
        instructions=instructions,
        include_param_descriptions=include_param_descriptions,
        include_return_description=include_return_description,
        metadata=metadata,
        config=config,
    )
    if fn is None:
        return functools.partial(tool, name=name, description=description, **kwargs)
    return Tool.from_function(fn, name=name, description=description, **kwargs)


def as_tools(
    tools: list[Union[Callable, langchain_core.tools.BaseTool, Tool]],
) -> list[Tool]:
    """
    Converts a list of tools (either Tool objects or callables) into a list of
    Tool objects.

    If duplicate tools are found, where the name, function, and coroutine are
    the same, only one is kept.
    """
    seen = set()
    new_tools = []
    for t in tools:
        if isinstance(t, Tool):
            continue
        elif isinstance(t, langchain_core.tools.BaseTool):
            t = Tool.from_lc_tool(t)
        elif inspect.isfunction(t):
            t = Tool.from_function(t)
        elif isinstance(t, dict):
            t = Tool(**t)
        else:
            raise ValueError(f"Invalid tool: {t}")

        if (t.name, t.description) in seen:
            continue
        new_tools.append(t)
        seen.add((t.name, t.description))
    return new_tools


def as_lc_tools(
    tools: list[Union[Callable, langchain_core.tools.BaseTool, Tool]],
) -> list[langchain_core.tools.BaseTool]:
    new_tools = []
    for t in tools:
        if isinstance(t, langchain_core.tools.BaseTool):
            continue
        elif isinstance(t, Tool):
            t = t.to_lc_tool()
        elif inspect.isfunction(t):
            t = langchain_core.tools.StructuredTool.from_function(t)
        else:
            raise ValueError(f"Invalid tool: {t}")
        new_tools.append(t)
    return new_tools


def output_to_string(output: Any) -> str:
    """
    Function outputs must be provided as strings
    """
    if output is None:
        return ""
    elif isinstance(output, str):
        return output
    try:
        return pydantic.TypeAdapter(type(output)).dump_json(output).decode()
    except Exception:
        return str(output)


class ToolResult(BaseModel):
    tool_call_id: str
    result: Any = Field(exclude=True, repr=False)
    str_result: str = Field(repr=False)
    is_error: bool = False
    is_private: bool = False
    end_turn: bool = False


def handle_tool_call(
    tool_call: Union[ToolCall, InvalidToolCall], tools: list[Tool]
) -> Any:
    """
    Given a ToolCall and set of available tools, runs the tool call and returns
    a ToolResult object,
    """
    is_error = False
    is_private = False
    end_turn = False
    tool = None
    tool_lookup = {t.name: t for t in tools}
    fn_name = tool_call["name"]

    if fn_name not in tool_lookup:
        fn_output = f'Function "{fn_name}" not found.'
        is_error = True
        is_private = True

    if not is_error:
        try:
            tool = tool_lookup[fn_name]
            fn_args = tool_call["args"]
            if isinstance(tool, Tool):
                fn_output = tool.run(input=fn_args)
                end_turn = tool.end_turn
            elif isinstance(tool, langchain_core.tools.BaseTool):
                fn_output = tool.invoke(input=fn_args)
            else:
                raise ValueError(f"Invalid tool: {tool}")
        except Exception as exc:
            fn_output = f'Error calling function "{fn_name}": {exc}'
            is_error = True

    return ToolResult(
        tool_call_id=tool_call["id"],
        result=fn_output,
        str_result=output_to_string(fn_output),
        is_error=is_error,
        is_private=getattr(tool, "private", is_private),
        end_turn=end_turn,
    )


async def handle_tool_call_async(
    tool_call: ToolCall | ChatCompletionMessageToolCall, tools: list[Tool]
) -> ToolResult:
    """
    Given a ToolCall and set of available tools, runs the tool call and returns
    a ToolResult object
    """
    if isinstance(tool_call, ChatCompletionMessageToolCall):
        tool_call = ToolCall(
            id=tool_call.id,
            name=tool_call.function.name,
            args=json.loads(tool_call.function.arguments),
        )
    is_error = False
    is_private = False
    end_turn = False
    tool = None
    tool_lookup = {t.name: t for t in tools}
    fn_name = tool_call["name"]

    if fn_name not in tool_lookup:
        fn_output = f'Function "{fn_name}" not found.'
        is_error = True
        is_private = True

    if not is_error:
        try:
            tool = tool_lookup[fn_name]
            fn_args = tool_call["args"]
            if isinstance(tool, Tool):
                fn_output = await tool.run_async(input=fn_args)
                end_turn = tool.end_turn
            elif isinstance(tool, langchain_core.tools.BaseTool):
                fn_output = await tool.ainvoke(input=fn_args)
            else:
                raise ValueError(f"Invalid tool: {tool}")
        except Exception as exc:
            fn_output = f'Error calling function "{fn_name}": {exc}'
            is_error = True

    return ToolResult(
        tool_call_id=tool_call["id"],
        result=fn_output,
        str_result=output_to_string(fn_output),
        is_error=is_error,
        is_private=getattr(tool, "private", is_private),
        end_turn=end_turn,
    )


def get_config_from_context(
    config_key: str | list[str] | None = None,
) -> Dict[str, Any]:
    """
    Get the RunContextToolkitConfig from the context
    For example for a 'default_database' toolkit_id, the config will be returned
    [{
        "toolkit_id": "default_database",
        "config": {
            "url": DatabaseSettings.objects.get_default_tenant_database().url,
            "database": DatabaseSettings.objects.get_default_tenant_database().database,
        }
    }]
    """
    from marvin.extensions.utilities.context import get_run_context

    context = get_run_context()
    pretty_log(context)
    if not context:
        return {}
    tool_configs = context.get("tool_config", [])
    config_keys = config_key if isinstance(config_key, list) else [config_key]
    for config_key in config_keys:
        for toolkit_config in tool_configs:
            if toolkit_config.get("toolkit_id") == config_key:
                return toolkit_config.get("config", {})
    return {}
