from typing import Callable, Dict, Literal
from .database import (
    db_query,
    db_list_tables,
    db_describe_tables,
    database_toolkit,
)
from .web_search import web_browser, web_browser_toolkit


class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def clear_tools(self):
        self.tools = {}

    def register_tool(self, name: str, tool: Callable):
        self.tools[name] = tool

    def get_tool(self, name: str):
        return self.tools.get(name)

    def bulk_register_tools(self, tools: Dict[str, Callable]):
        self.tools.update(tools)


class ToolkitRegistry:
    def __init__(self):
        self.toolkits = {}

    def clear_toolkits(self):
        self.toolkits = {}

    def register_toolkit(self, name: str, toolkit: Callable):
        self.toolkits[name] = toolkit

    def get_toolkit(self, name: str):
        return self.toolkits.get(name)

    def bulk_register_toolkits(self, toolkits: Dict[str, Callable]):
        self.toolkits.update(toolkits)


all_tools = {
    "db_query": db_query,
    "db_list_tables": db_list_tables,
    "db_describe_tables": db_describe_tables,
    "web_browser": web_browser,
}

tool_registry = ToolRegistry()
tool_registry.bulk_register_tools(all_tools)


def get_all_tools():
    """
    Returns a dictionary of all available tools.
    """
    return all_tools


def get_tool_by_name(name: str):
    """
    Returns a specific tool function by its name.
    """
    return tool_registry.get_tool(name)


def get_toolkit_by_id(toolkit_id: str):
    """
    Returns a specific toolkit by its id.
    """
    toolkit = toolkit_registry.get_toolkit(toolkit_id)
    if toolkit:
        return toolkit
    raise ValueError(f"Toolkit with id {toolkit_id} not found")


toolkits = [
    database_toolkit,
    web_browser_toolkit,
]

all_toolkits = {
    "database": database_toolkit,
    "web_browser": web_browser_toolkit,
}

AvailableToolkits = Literal[
    "database",
    "web_browser",
]

toolkit_registry = ToolkitRegistry()
toolkit_registry.bulk_register_toolkits(all_toolkits)

__all__ = [
    "get_all_tools",
    "get_tool_specs",
    "get_tool_by_name",
    "get_tool_spec_by_name",
] + list(all_tools.keys())
