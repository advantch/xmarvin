from apps.ai.agent.monitoring.logging import pretty_log
from apps.databases.models import DatabaseSettings

from marvin.extensions.tools.app_tools import all_tools, toolkits
from marvin.extensions.tools.tool import Tool


def add_db_config(tool: Tool):
    tenant_db = DatabaseSettings.objects.get_default_tenant_database()
    if tenant_db:
        tool.config = {
            "url": tenant_db.connection_string,
            "readonly": tenant_db.is_readonly,
        }
    return tool


def get_agent_tools(agent_config, is_assistant=False) -> tuple[list[Tool], dict]:
    from apps.ai.models import CustomToolkit

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

    # Handle custom toolkits
    agent_toolkits = CustomToolkit.objects.filter(
        agents=agent_config.id, is_active=True
    )
    for agent_toolkit in agent_toolkits:
        toolkit = next((t for t in toolkits if t.id == agent_toolkit.toolkit_id), None)
        if not toolkit:
            continue
        # update config
        toolkit.config = agent_toolkit.get_config()
        if toolkit.requires_config:
            config.append({'toolkit_id': toolkit.id, 'config': toolkit.config})
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
