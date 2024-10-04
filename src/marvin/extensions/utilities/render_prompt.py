import inspect
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from jinja2 import Environment as JinjaEnvironment
from jinja2 import StrictUndefined, Template, select_autoescape

from .prompts import DEFAULT_ASSISTANT_PROMPT, DEFAULT_PROMPT

global_fns = {
    "now": lambda: datetime.now(ZoneInfo("UTC")),
    "inspect": inspect,
    "getcwd": os.getcwd,
    "zip": zip,
}

prompt_env = JinjaEnvironment(
    # loader=PackageLoader("marvin.extensions", "prompts"),
    autoescape=select_autoescape(default_for_string=False),
    trim_blocks=True,
    lstrip_blocks=True,
    auto_reload=True,
    undefined=StrictUndefined,
)

prompt_env.globals.update(global_fns)


def render_instructions(agent_config=None):
    """
    Render the system prompt with the given agent config.
    """
    from marvin.extensions.types import AgentConfig

    agent_config = agent_config or AgentConfig.default_agent()
    prompt = agent_config.instructions.text or DEFAULT_PROMPT
    t = Template(prompt)
    c = {"agent_config": agent_config, "date": datetime.now().isoformat()}
    prompt_str = t.render(c)
    return prompt_str


def render_assistant_instructions(agent_config):
    prompt = agent_config.instructions.text or DEFAULT_ASSISTANT_PROMPT
    t = Template(prompt)
    c = {"agent_config": agent_config, "date": datetime.now().isoformat()}
    prompt_str = t.render(c)
    return prompt_str


def render_template(template_str, context):
    t = Template.from_string(template_str)
    return t.render(context)


def compile_prompt(agent_config) -> str:
    """
    Compile the prompt for the current turn.

    Returns:
        str: The compiled prompt.
    """
    from marvin.extensions.prompt_templates.prompt_templates import (
        InstructionsTemplate,
        MemoryTemplate,
        ToolTemplate,
    )

    prompts = [
        ToolTemplate(tools=agent_config.get_tools()).render(),
        MemoryTemplate(memories=agent_config.get_memories()).render(),
        InstructionsTemplate(instructions=agent_config.get_instructions()).render(),
    ]

    prompt = "\n\n".join([p for p in prompts if p])
    return prompt
