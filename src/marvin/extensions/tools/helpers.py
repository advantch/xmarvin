from marvin.extensions.tools.app_tools import all_tools, toolkits
from marvin.extensions.tools.tool import Tool
from marvin.extensions.utilities.logging import pretty_log
from typing import List

def get_agent_tools(agent_config, is_assistant=False) -> tuple[List[Tool], dict]:
    all_agent_tools = []
    config = []

    # Handle standard toolkits
    for toolkit_id in agent_config.builtin_toolkits:
        toolkit = next((t for t in toolkits if t.id == toolkit_id), None)
        if not toolkit:
            continue
        for tool in toolkit.to_tool_list():
            code_tool = all_tools.get(tool.name)
            if code_tool:
                all_agent_tools.append(code_tool)

    pretty_log(f"Agent {agent_config.name} has {all_agent_tools} tools")
    if is_assistant:
        return [t.function_tool() for t in all_agent_tools], config

    return all_agent_tools, config


def get_tool(tool_id: str) -> Tool:
    return all_tools.get(tool_id)
