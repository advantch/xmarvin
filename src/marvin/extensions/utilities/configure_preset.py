from .prompts import SQL_PROMPT
from marvin.extensions.types import StartRunSchema
from marvin.extensions.types import AgentConfig
from marvin.extensions.types.llms import AIModels


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

    # # append table names to reduce latency.
    # table_names = get_table_names()
    # data.message.append_content(str(table_names))

    return data
