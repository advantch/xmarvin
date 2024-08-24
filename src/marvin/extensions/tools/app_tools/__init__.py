from typing import Literal
from .database import (
    db_query,
    db_list_tables,
    db_describe_tables,
    db_create_table,
    db_update_table,
    db_drop_table,
    default_database_toolkit,
)
from .web_search import web_browser, web_browser_toolkit

all_tools = {
    "db_query": db_query,
    "db_list_tables": db_list_tables,
    "db_describe_tables": db_describe_tables,
    "db_create_table": db_create_table,
    "db_update_table": db_update_table,
    "db_drop_table": db_drop_table,
    "web_browser": web_browser,
}


def get_all_tools():
    """
    Returns a dictionary of all available tools.
    """
    return all_tools


def get_tool_by_name(name: str):
    """
    Returns a specific tool function by its name.
    """
    return all_tools.get(name)

def get_toolkit_by_id(toolkit_id: str):
    for toolkit in toolkits:
        if toolkit.id == toolkit_id:
            return toolkit
    raise ValueError(f"Toolkit with id {toolkit_id} not found")

__all__ = [
    "get_all_tools",
    "get_tool_specs",
    "get_tool_by_name",
    "get_tool_spec_by_name",
] + list(all_tools.keys())

toolkits = [
    default_database_toolkit,
    web_browser_toolkit,
]

AvailableToolkits = Literal[
    "database",
    "default_database",
    "image_generation",
    "web_browser",
    "search",
    "transcriber",
    "cms",
    "sec",
    "code_interpreter",
    "microsoft_outlook",
    "user_enrichment",
]
