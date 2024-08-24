from apps.ai.agent.utilities.prompts import DEFAULT_ASSISTANT_PROMPT, DEFAULT_PROMPT
from django.template import Context, Template
from django.utils import timezone


def render_instructions(agent_config=None, prompt=None):
    """
    Render the system prompt with the given agent config.
    """
    from marvin.extensions.types import AgentConfig

    agent_config = agent_config or AgentConfig.default_agent()
    prompt = prompt or DEFAULT_PROMPT
    t = Template(prompt)
    c = Context({"agent_config": agent_config, "date": timezone.now().isoformat()})
    prompt_str = t.render(c)
    return prompt_str


def render_assistant_instructions(agent_config):
    prompt = DEFAULT_ASSISTANT_PROMPT
    t = Template(prompt)
    c = Context({"agent_config": agent_config, "date": timezone.now().isoformat()})
    prompt_str = t.render(c)
    return prompt_str


def render_template(template_str, context):
    t = Template(template_str)
    c = Context(context)
    return t.render(c)
