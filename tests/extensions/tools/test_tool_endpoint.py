import pytest
from django.urls import reverse
from django.test import Client
from marvin.extensions.tools.app_tools import get_all_tools, all_tools
from marvin.extensions.tools.tool_runner import fetch_and_run_tool
from marvin.extensions.storage.simple_chatstore import SimpleJsonStorage
from marvin.extensions.tools.tool import Tool
import inspect


@pytest.fixture
def client():
    return Client()


@pytest.mark.parametrize("tool_name", get_all_tools().keys())
@pytest.mark.django_db
def test_tool_direct(tool_name):
    tool_function = all_tools[tool_name]
    params = inspect.signature(tool_function).parameters
    mock_input = {param: "test_value" for param in params}
    result = tool_function(**mock_input)
    assert result is not None


@pytest.mark.parametrize("tool_name", get_all_tools().keys())
@pytest.mark.django_db
def test_tool_via_runner(tool_name):
    tool_function = all_tools[tool_name]
    import inspect

    params = inspect.signature(tool_function).parameters
    mock_input = {param: "test_value" for param in params}
    result = fetch_and_run_tool(tool_name, mock_input)
    assert result is not None


@pytest.mark.django_db
def test_run_tool_api(client):
    url = reverse("run_tool")  # Make sure this matches the name in your urls.py
    for tool_name, tool_function in all_tools.items():
        import inspect

        params = inspect.signature(tool_function).parameters
        mock_input = {param: "test_value" for param in params}
        data = {"tool_id": tool_name, "config": {}, "input_data": mock_input}
        response = client.post(url, data=data, content_type="application/json")
        assert response.status_code == 200
        assert "result" in response.json()


@pytest.mark.django_db
def test_run_tool_from_db():
    for tool_name, tool_function in all_tools.items():
        db_tool = SimpleJsonStorage.create(
            name=f"Mock {tool_name}",
            system_description=f"A mock {tool_name} tool",
            data={
                "fn": tool_function,
                "parameters": {
                    param: {"type": "string"}
                    for param in inspect.signature(tool_function).parameters
                },
            },
        )
        params = inspect.signature(tool_function).parameters
        mock_input = {param: "test_value" for param in params}

        result = fetch_and_run_tool(str(db_tool.id), mock_input)
        assert result is not None


@pytest.mark.django_db
def test_run_nonexistent_tool():
    with pytest.raises(ValueError, match="Tool with id .* not found"):
        fetch_and_run_tool("nonexistent_tool_id", {})


@pytest.mark.django_db
def test_tool_specs(tool_specs):
    for tool_spec in tool_specs:
        assert isinstance(tool_spec, Tool)
        assert tool_spec.name is not None
        assert tool_spec.description is not None
        assert isinstance(tool_spec.parameters, dict)
