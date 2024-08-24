import uuid
from typing import Callable, List, Literal, Optional, Union
from uuid import UUID

from marvin.beta.assistants import CodeInterpreter, FileSearch
from marvin.beta.local import LocalAssistant
from marvin.extensions.tools.services.db import get_django_db_connection_url
from marvin.extensions.tools.tool import Tool
from marvin.extensions.types.base import BaseSchemaConfig
from marvin.extensions.types.llms import AIModels
from marvin.extensions.utilities.prompts import DEFAULT_ASSISTANT_BASE_PROMPT
from marvin.extensions.utilities.render_prompt import (
    render_assistant_instructions,
    render_instructions,
)
from marvin.tools.assistants import AssistantTool
from pydantic import BaseModel, Field

OPENAI_TOOLS = ["code_interpreter", "file_search"]


class AgentApiTool(BaseModel):
    """
    Agent tool config
    """

    name: str | None = None
    custom_name: str | None = None
    custom_description: str | None = None
    instructions: str | None = None
    parameters: dict | None = None
    metadata: dict | None = None
    config: dict | BaseModel | None = None
    settings: dict | None = None
    private: bool | None = None
    end_turn: bool | None = None
    db_id: str | uuid.UUID | None = None
    fn: dict | None = None
    auto_run: bool | None = True
    tool_id: str | None = None

    class Config(BaseSchemaConfig):
        pass

    @classmethod
    def from_tool(cls, tool, config: dict = None):
        dict_tool = tool.model_dump()
        dict_tool["fn"] = None
        dict_tool["tool_id"] = tool.db_id if tool.db_id else tool.name
        if config:
            dict_tool["config"] = config
        else:
            dict_tool["config"] = {}
        return cls(**dict_tool)


class TiptapNode(BaseModel):
    type: str
    content: Optional[list["TiptapNode"]] = None
    attrs: Optional[dict] = None
    marks: Optional[list[dict]] = None
    text: Optional[str] = None

    class Config:
        extra = "allow"


class TiptapDoc(BaseModel):
    type: Literal["doc"]
    content: list[TiptapNode] | None = None


class AgentInstructions(BaseModel):
    text: str | None = None
    json_doc: TiptapDoc | None = Field(default=None, alias="json")

    class Config(BaseSchemaConfig):
        pass


class RuntimeConfig(BaseModel):
    page_id: str | UUID | None = None
    document_context: str | None = None
    include_document: bool | None = True

    class Config(BaseSchemaConfig):
        pass


class CustomToolkit(BaseModel):
    toolkit_id: str
    db_id: str


class AgentConfig(BaseModel):
    """
    Defines attributes for agents and assistants(openai)

    """

    id: Optional[Union[str, uuid.UUID]] = None
    external_id: str | UUID | None = None
    name: Optional[str] | None = None
    unique_name: Optional[str] | None = Field(
        default=None, description="Unique name for the agent used in flows."
    )
    description: Optional[str] | None = None
    system_prompt: Optional[str | dict] | None = None
    temperature: Optional[float] | None = 0
    instructions: AgentInstructions | None = None
    owner_id: Optional[str] | None = None

    # tools & toolkits
    builtin_toolkits: List[str] = Field(
        default_factory=list, description="List of standard toolkit IDs"
    )
    custom_toolkits: List[CustomToolkit] = Field(
        default_factory=list, description="List of custom toolkit IDs"
    )
    toolkit_config: dict | None = None
    runtime_tools: list[Callable | Tool | AssistantTool] | None = None

    model: AIModels | None = AIModels.GPT_4O_MINI
    onboarding_instructions: Optional[str] | None = Field(
        default=None, description="Onboarding instructions for users."
    )
    mode: Literal["agent", "assistant"] | None = None
    starters: Optional[list] | None = None
    settings: dict | None = {}
    tenant_id: Optional[Union[str, uuid.UUID]] | None = None
    runtime_config: RuntimeConfig | None = None
    user_access: bool | None = Field(
        default=False, description="Require user access on each run."
    )

    # file search
    file_search_enabled: bool | None = None
    max_runs: int | None = 10
    search_all_files: bool | None = None
    use_optimised_prompt: bool | None = False
    # system
    is_internal: bool | None = False

    class Config(BaseSchemaConfig):
        pass

    def construct_unique_name(self):
        short_id = str(self.id)[:4]
        return f"{self.name}-{short_id}"

    @classmethod
    def default_agent(cls, model=None):
        default_model = AIModels.GPT_4O_MINI
        instructions = DEFAULT_ASSISTANT_BASE_PROMPT.format(
            date=timezone.now().isoformat()
        )
        from marvin.extensions.tools.app_tools import (
            code_interpreter_toolkit,
            search_toolkit,
            web_browser_toolkit,
        )

        return cls(
            name="Default Assistant",
            model=model or default_model,
            mode="assistant",
            description="Default agent",
            system_prompt=instructions,
            instructions={
                "json": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": instructions}],
                        },
                    ],
                },
                "text": "You are a helpful assistant.",
            },
            triggers=[],
            is_document=False,
            include_document=False,
            settings={},
            use_citations=True,
            builtin_toolkits=[
                web_browser_toolkit.id,
                search_toolkit.id,
                code_interpreter_toolkit.id,
            ],
            starters=[
                {
                    "value": "Search google for AI tools",
                    "title": "Search google for AI tools",
                },
                {
                    "value": "What is vanty.ai",
                    "title": "What is vanty.ai",
                },
            ],
        )

    @classmethod
    def admin_agent(cls, model=None):
        default_model = AIModels.GPT_4O

        agent_config = cls(
            name="Admin Agent",
            is_internal=True,
            model=model or default_model,
            tools=[],
            description="Default agent",
            system_prompt="You are a helpful assistant.",
            instructions={
                "json": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "You are a helpful assistant.",
                                },
                            ],
                        }
                    ],
                },
                "text": "You are a helpful assistant.",
            },
            triggers=[],
            is_document=False,
            include_document=False,
            settings={},
            use_citations=True,
            starters=[
                {
                    "value": "How many users are there?",
                    "title": "Number of users",
                },
                {
                    "value": "How many workspaces have been created?",
                    "title": "Number of workspaces",
                },
            ],
        )
        agent_config.toolkit_config = {
            "database": {
                "url": get_django_db_connection_url(db_alias="default"),
                "readonly": False,
            }
        }
        return agent_config

    def get_assistant_tools(self) -> list[Callable | AssistantTool]:
        """
        Fetch agent tools for openai assistants
        Returns a list of functions for assistant to use.

        Only use this for openai assistants.
         - code interpreter & filesearch are not supported for other agents.
         - file search
        """
        from marvin.extensions.tools.getters import get_agent_tools

        tools = []
        agent_tools, config = get_agent_tools(self, is_assistant=True)
        for t in agent_tools:
            if t.function.name == "file_search":
                tools.append(FileSearch)
            elif t.function.name == "code_interpreter":
                tools.append(CodeInterpreter)
            else:
                tools.append(t)

        self.toolkit_config = config
        self.runtime_tools = tools
        return tools

    def get_tools(self) -> list[AgentApiTool]:
        """
        Fetch agent tools for agents
        Returns a list of functions for agent to use.
        """
        from marvin.extensions.tools.getters import get_agent_tools

        tools, config = get_agent_tools(self)
        self.toolkit_config = config
        return tools

    def agent_tools_to_function_tools(self) -> list[AgentApiTool]:
        """
        #TODO check usage should this be split and return a FunctionTool from openai?
        """
        tools = self.get_tools()
        return [AgentApiTool.from_tool(tool) for tool in tools]

    def get_instructions(self, simple=False):
        if simple:
            return self.instructions.text
        if self.mode == "assistant":
            return render_assistant_instructions(self)
        else:
            return render_instructions(self)

    def as_assistant(self):
        return LocalAssistant(
            id=self.id or str(uuid.uuid4()),
            name=self.name,
            instructions=self.get_instructions(),
            tools=self.get_tools(),
            model=self.model,
        )
