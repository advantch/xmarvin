import uuid
from typing import Callable, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from marvin.extensions.agent_memory.memory import Memory
from marvin.extensions.types.base import BaseModelConfig
from marvin.extensions.types.llms import AIModels
from marvin.extensions.utilities.render_prompt import (
    render_assistant_instructions,
    render_instructions,
)
from marvin.tools.assistants import AssistantTool

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

    class Config(BaseModelConfig):
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
    content: Optional[List["TiptapNode"]] = None
    attrs: Optional[dict] = None
    marks: Optional[List[dict]] = None
    text: Optional[str] = None

    class Config:
        extra = "allow"


class TiptapDoc(BaseModel):
    type: Literal["doc"]
    content: List[TiptapNode] | None = None


class AgentInstructions(BaseModel):
    text: str | None = None
    json_doc: TiptapDoc | None = Field(default=None, alias="json")

    class Config(BaseModelConfig):
        pass


class RuntimeConfig(BaseModel):
    page_id: str | UUID | None = Field(
        default=None, description="Page ID to use for the agent if working with editors"
    )
    document_context: str | None = Field(
        default=None,
        description="Document context to use for the agent if working with editors",
    )
    include_document: bool | None = Field(
        default=None, description="Include document in the context"
    )
    model: AIModels | None = Field(
        default=None, description="Model to use for the agent"
    )
    extra: dict | None = Field(
        default=None, description="Extra runtime config for agents"
    )

    class Config(BaseModelConfig):
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

    memories: List[Memory] = Field(
        default_factory=list, description="List of memories for the agent"
    )

    # tools & toolkits
    builtin_toolkits: List[str] = Field(
        default_factory=list, description="List of standard toolkit IDs"
    )
    custom_toolkits: List[CustomToolkit] = Field(
        default_factory=list, description="List of custom toolkit IDs"
    )
    toolkit_config: dict | List[dict] | None = None

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
    vector_store_id: str | None = None
    file_ids: List[str] | None = Field(default_factory=list)
    search_all_files: bool | None = None

    max_runs: int | None = 10

    use_optimised_prompt: bool | None = False

    # system
    is_internal: bool | None = False

    class Config(BaseModelConfig):
        pass

    def construct_unique_name(self):
        short_id = str(self.id)[:4]
        return f"{self.name}-{short_id}"

    def get_assistant_tools(self) -> List[Callable | AssistantTool]:
        """
        Fetch tools for *assistant running on openai*
        Returns a list of functions for assistant to use.
         - code interpreter & filesearch are not supported for other agents.
         - file search
        """
        from marvin.extensions.tools.helpers import get_agent_tools  # noqa
        from marvin.beta.assistants import CodeInterpreter, FileSearch  # noqa

        tools = []
        agent_tools, config = get_agent_tools(self, is_assistant=True)
        for t in agent_tools:
            # native file search
            if t.function.name == "file_search":
                tools.append(FileSearch)
            # native code interpreter if applicable
            elif t.function.name == "code_interpreter":
                tools.append(CodeInterpreter)
            else:
                tools.append(t)
        # remote
        if "code_interpreter" in self.builtin_toolkits and CodeInterpreter not in tools:
            tools.append(CodeInterpreter)
        if "file_search" in self.builtin_toolkits and FileSearch not in tools:
            tools.append(FileSearch)

        self.toolkit_config = [config] if config else []
        return tools

    def get_memories(self) -> List[Memory]:
        """
        Fetch memories for the agent
        """
        return self.memories

    def get_tools(self) -> List[AgentApiTool]:
        """
        Fetch agent tools for agents
        Returns a list of functions for agent to use.
        """
        from marvin.extensions.tools.helpers import get_agent_tools

        tools, config = get_agent_tools(self)
        self.toolkit_config = [config] if config else []
        return tools

    def agent_tools_to_function_tools(self) -> List[AgentApiTool]:
        """
        Agent tools to function tools
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
        from marvin.beta.local.assistant import LocalAssistant

        return LocalAssistant(
            id=self.id or str(uuid.uuid4()),
            name=self.name,
            instructions=self.get_instructions(),
            tools=self.get_tools(),
            model=self.model,
        )

    @classmethod
    def default_agent(cls, model=None):
        default_model = AIModels.GPT_4O_MINI
        instructions = "You are a helpful assistant."
        from marvin.extensions.tools.app_tools import web_browser_toolkit

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
            builtin_toolkits=[web_browser_toolkit.id],
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
