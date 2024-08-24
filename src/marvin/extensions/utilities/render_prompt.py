from datetime import datetime

from jinja2 import Template

from .prompts import DEFAULT_ASSISTANT_PROMPT, DEFAULT_PROMPT


def render_instructions(agent_config=None, prompt=None):
    """
    Render the system prompt with the given agent config.
    """
    from marvin.extensions.types import AgentConfig

    agent_config = agent_config or AgentConfig.default_agent()
    prompt = prompt or DEFAULT_PROMPT
    t = Template.from_string(prompt)
    c = {"agent_config": agent_config, "date": datetime.now().isoformat()}
    prompt_str = t.render(c)
    return prompt_str


def render_assistant_instructions(agent_config):
    prompt = DEFAULT_ASSISTANT_PROMPT
    t = Template(prompt)
    c = {"agent_config": agent_config, "date": datetime.now().isoformat()}
    prompt_str = t.render(c)
    return prompt_str


def render_template(template_str, context):
    t = Template.from_string(template_str)
    return t.render(context)
