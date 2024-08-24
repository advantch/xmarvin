import uuid

from apps.ai.agent.monitoring.logging import pretty_log
from apps.ai.models.tools import Tool as DBTool

from marvin.extensions.tools.app_tools import get_tool_by_name, toolkits
from marvin.extensions.tools.context import tool_run_context
from marvin.extensions.utilities.serialization import to_serializable


def get_toolkit_by_id(toolkit_id: str):
    for toolkit in toolkits:
        if toolkit.id == toolkit_id:
            return toolkit
    raise ValueError(f"Toolkit with id {toolkit_id} not found")


def fetch_and_run_tool(
    tool_id: str,
    input_data: dict,
    config: dict = None,
    toolkit_id: str | uuid.UUID | None = None,
    db_id: str | uuid.UUID | None = None,
):
    tool = get_tool_by_name(tool_id)
    config = config or {}
    if tool and db_id:
        db_tool = DBTool.objects.filter(id=db_id).first()
        if db_tool:
            tool.db_id = db_tool.id
            tool.config = db_tool.get_config()
            config = tool.config
        else:
            raise ValueError(f"Tool with id {tool_id} not found")
    result = None
    with tool_run_context(tool_id, config, input_data, toolkit_id) as (run, context):
        result = tool.run(input_data)

        # Update run with result
        run.data["outputs"] = to_serializable(result)
        run.save()

    return result

def fetch_and_run_toolkit_tool(
    tool_id: str,
    toolkit_id: str,
    input_data: dict,
    config: dict = None,
    db_id: str | uuid.UUID | None = None,
):
    config = config or {}

    from apps.ai.models import CustomToolkit

    if db_id:
        custom_toolkit = CustomToolkit.objects.filter(id=db_id).first()
        if custom_toolkit:
            toolkit = get_toolkit_by_id(custom_toolkit.toolkit_id)
            tool = toolkit.get_tool(tool_id)
            config.update(custom_toolkit.config)
        else:
            raise ValueError(f"Custom toolkit with id {toolkit_id} not found")
    elif toolkit_id:
        toolkit = get_toolkit_by_id(toolkit_id)
        tool = toolkit.get_runnable_tool(tool_id)

    if not tool or not tool.run or not tool.fn:
        raise ValueError(f"Tool with id {tool_id} not found or is invalid")
    result = {"run_id": None, "result": None}
    with tool_run_context(tool_id, config, input_data, toolkit_id) as (run, context):
        result["run_id"] = run.id
        result["result"] = tool.run(input_data)

        # Update run with result
        run.data["outputs"] = to_serializable(result)
        pretty_log(result)
        run.save()

    return result