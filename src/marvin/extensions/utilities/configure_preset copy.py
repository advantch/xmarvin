from marvin.extensions.types import AgentConfig, StartRunSchema
from marvin.extensions.types.llms import AIModels

from .prompts import SQL_PROMPT


def configure_internal_sql_agent(data: StartRunSchema) -> str:
    """
    Configure SQL agent
    """
    data.agent_config = AgentConfig.admin_agent()
    data.agent_config.instructions = {
        "json": {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": SQL_PROMPT}],
                }
            ],
        },
        "text": SQL_PROMPT,
    }
    data.agent_config.model = AIModels.GPT_4O
    data.agent_config.mode = "assistant"

    return data
