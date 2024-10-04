from typing import Optional

from pydantic import BaseModel, model_validator

from marvin.extensions.agent_memory.memory import Memory
from marvin.extensions.tools.tool import Tool
from marvin.extensions.types.agent import AgentConfig
from marvin.extensions.utilities.render_prompt import prompt_env


class Template(BaseModel):
    model_config = dict(extra="allow")
    template: Optional[str] = None
    template_path: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self):
        if not self.template and not self.template_path:
            raise ValueError("Template or template_path must be provided.")
        return self

    def render(self, **kwargs) -> str:
        if not self.should_render():
            return ""

        render_kwargs = dict(self)
        del render_kwargs["template"]
        del render_kwargs["template_path"]

        if self.template is not None:
            template = prompt_env.from_string(self.template)
        else:
            template = prompt_env.get_template(self.template_path)
        return template.render(**render_kwargs | kwargs)

    def should_render(self) -> bool:
        return True


class AgentTemplate(Template):
    template_path: str = "agent.jinja"
    agent: AgentConfig


class InstructionsTemplate(Template):
    template_path: str = "instructions.jinja"
    instructions: list[str] = []

    def should_render(self) -> bool:
        return bool(self.instructions)


class ToolTemplate(Template):
    template_path: str = "tools.jinja"
    tools: list[Tool]

    def should_render(self) -> bool:
        return any(t.instructions for t in self.tools)


class MemoryTemplate(Template):
    template_path: str = "memories.jinja"
    memories: list[Memory]

    def should_render(self) -> bool:
        return bool(self.memories)
