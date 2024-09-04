from typing import List, Literal

from pydantic import BaseModel, Field, computed_field, model_validator

from marvin.extensions.tools.tool import ApiTool, Tool
from marvin.extensions.types.base import BaseModelConfig


class ToolKitTokenIntegration(BaseModel):
    id: str = Field(description="DB ID of the token integration")
    type: Literal["oauth", "api"] = Field(
        description="Type of token for the toolkit", default="oauth"
    )
    active: bool = Field(description="Whether the integration is active", default=True)


class ToolKit(BaseModel):
    id: str = Field(description="DB ID of the toolkit")
    name: str = Field(description="Name of the toolkit")
    description: str = Field(description="Description of the toolkit")
    tools: List[ApiTool] | None = Field(
        description="List of tools in the toolkit", default=None
    )
    tool_ids: List[str] | None = Field(
        description="List of tool IDs in the toolkit", default=None
    )
    requires_config: bool = Field(
        description="Whether the toolkit requires a config", default=False
    )
    config_type: Literal["static", "integration"] = Field(
        description="Type of config for the toolkit", default="static"
    )
    config_schema: dict | None = Field(
        description="Configuration schema for the toolkit", default=None
    )
    config: dict | None = Field(
        description="Configuration for the toolkit", default=None
    )
    db_id: str | None = Field(description="Database ID for the toolkit", default=None)
    categories: List[str] = Field(
        description="Categories for the toolkit", default=None
    )
    active_tools: List[str] = Field(
        description="Active tools for the toolkit", default=None
    )
    icon: str | None = Field(description="Icon for the toolkit", default=None)
    requires_integration: bool = Field(
        description="Whether the toolkit requires an integration", default=False
    )
    integrations: List[ToolKitTokenIntegration] | None = Field(
        description="List of integrations for the toolkit", default=None
    )

    class Config(BaseModelConfig):
        pass

    @model_validator(mode="after")
    def validate_tools(self):
        if self.tools is None and self.tool_ids is None:
            raise ValueError("Either tools or tool_ids must be provided")
        return self

    @model_validator(mode="after")
    def validate_active_tools(self):
        if self.active_tools is None or (
            isinstance(self.active_tools, list) and len(self.active_tools) == 0
        ):
            self.active_tools = [t.name for t in self.tools]
        return self

    @computed_field
    def actions(self) -> int:
        return len(self.tools)

    def to_tool_list(self) -> List[ApiTool]:
        tools = []
        from .helpers import get_tool  # noqa

        if self.tools is not None:
            tools.extend(self.tools)
        if self.tool_ids is not None:
            tools.extend([get_tool(tool_id) for tool_id in self.tool_ids])
        return tools

    def to_runnable_tool_list(self) -> List[Tool]:
        tools = []
        from .helpers import get_tool  # noqa

        if self.tools is not None:
            tools.extend(self.tools)
        if self.tool_ids is not None:
            tools.extend([get_tool(tool_id) for tool_id in self.tool_ids])
        return tools

    def list_tools(self) -> List[str]:
        return [t.name for t in self.to_tool_list()]

    def get_tool(self, tool_name: str) -> ApiTool:
        for t in self.to_tool_list():
            if t.name == tool_name:
                return t
        raise ValueError(f"Tool '{tool_name}' not found in toolkit.")

    def get_runnable_tool(self, tool_name: str) -> Tool:
        from .app_tools import get_tool_by_name

        for t in self.to_runnable_tool_list():
            if t.name == tool_name:
                return get_tool_by_name(tool_name)
        raise ValueError(f"Tool '{tool_name}' not found in toolkit.")

    def add_tool(self, tool: ApiTool):
        if isinstance(tool, Tool):
            tool = ApiTool(**tool.model_dump())
        self.tools.append(tool)

    def remove_tool(self, tool_name: str):
        self.tools = [t for t in self.tools if t.name != tool_name]

    @classmethod
    def create_toolkit(
        cls,
        id: str,
        tools: List[ApiTool],
        name: str,
        description: str,
        requires_config: bool = False,
        config: dict | None = None,
        config_schema: dict | None = None,
        categories: List[str] = [],
        icon: str | None = None,
        requires_integration: bool = False,
        config_type: Literal["static", "integration"] = "static",
    ):
        return cls(
            name=name,
            id=id,
            description=description,
            tools=[ApiTool(**t.model_dump()) for t in tools],
            requires_config=requires_config,
            config=config,
            config_schema=config_schema,
            categories=categories,
            icon=icon,
            requires_integration=requires_integration,
            config_type=config_type,
        )
