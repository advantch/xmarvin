from enum import Enum


class AIModels(str, Enum):
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4O = "gpt-4o"
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20240620"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    COMMAND_PLUS = "command-plus"
    COMMAND_PLUS_R = "command-plus-r"
    GEMINI_FLASH = "gemini-flash"

    @staticmethod
    def provider(model: str):
        if model in [
            AIModels.CLAUDE_3_OPUS,
            AIModels.CLAUDE_3_HAIKU,
            AIModels.CLAUDE_3_5_SONNET,
            AIModels.CLAUDE_3_SONNET,
        ]:
            return "anthropic"

        if model in [AIModels.GEMINI_FLASH]:
            return "google"

        if model in [AIModels.GPT_4O_MINI, AIModels.GPT_4O]:
            return "openai"

        if model in [AIModels.COMMAND_PLUS, AIModels.COMMAND_PLUS_R]:
            return "cohere"

        return "openai"
