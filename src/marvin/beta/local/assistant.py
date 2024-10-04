import uuid
from pathlib import Path
from typing import List, Optional, Union

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from pydantic import BaseModel, Field
from rich.console import Console
from rich.prompt import Confirm

from marvin.extensions.storage import BaseMessageStore
from marvin.extensions.tools.tool import Tool
from marvin.extensions.types.agent import AgentConfig
from marvin.tools.filesystem import (
    generate_constrained_concat,
    generate_constrained_delete,
    generate_constrained_write,
)
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, run_async, run_sync

console = Console()
assistants_app = typer.Typer(no_args_is_help=True)

ASSISTANTS_DIR = Path.home() / ".marvin/cli/assistants"
SCRATCHPAD_DIR = ASSISTANTS_DIR / "scratchpad"

constrained_write = generate_constrained_write(SCRATCHPAD_DIR)
constrained_delete = generate_constrained_delete(SCRATCHPAD_DIR)
constrained_concat = generate_constrained_concat(SCRATCHPAD_DIR)


class LocalAssistant(BaseModel, ExposeSyncMethodsMixin):
    id: str | None | uuid.UUID = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str | None = None
    instructions: str | None = None
    tools: List[Tool] | None = Field(default_factory=list)
    model: str | None = None
    file_ids: List[str] | None = Field(default_factory=list)
    vector_store_id: str | None = None
    storage: Optional[type[BaseMessageStore]] = None

    def run(self, thread, **kwargs):
        from .run import LocalRun  # noqa: F401

        return LocalRun(assistant=self, thread=thread, **kwargs)

    @classmethod
    def from_agent_config(cls, agent_config: AgentConfig):
        return cls(
            id=agent_config.id or str(uuid.uuid4()),
            name=agent_config.name,
            instructions=agent_config.get_instructions(),
            tools=agent_config.get_tools(),
            model=agent_config.model,
            file_ids=agent_config.file_ids,
            vector_store_id=agent_config.vector_store_id,
        )

    @classmethod
    async def from_agent_config_async(cls, agent_config):
        return await run_sync(cls.from_agent_config)(agent_config)

    def chat(
        self,
        initial_message: str = None,
        assistant_dir: Union[Path, str, None] = None,
        **kwargs,
    ):
        """Start a chat session with the assistant."""
        return run_sync(self.chat_async(initial_message, assistant_dir, **kwargs))

    async def chat_async(
        self,
        initial_message: str = None,
        assistant_dir: Union[Path, str, None] = None,
        **kwargs,
    ):
        """Async method to start a chat session with the assistant."""
        assistant_dir = assistant_dir or ASSISTANTS_DIR
        history_path = Path(assistant_dir) / "chat_history.txt"
        if not history_path.exists():
            history_path.parent.mkdir(parents=True, exist_ok=True)

        session = PromptSession(
            history=FileHistory(str(history_path.absolute().resolve()))
        )
        # send an initial message, if provided
        if initial_message is not None:
            await self.say_async(initial_message, **kwargs)
        while True:
            try:
                message = await run_async(
                    session.prompt,
                    message="➤ ",
                    auto_suggest=AutoSuggestFromHistory(),
                )
                # if the user types exit, ask for confirmation
                if message in ["exit", "!exit", ":q", "!quit"]:
                    if Confirm.ask("[red]Are you sure you want to exit?[/]"):
                        break
                    continue
                # if the user types exit -y, quit right away
                elif message in ["exit -y", ":q!"]:
                    break
                await self.say_async(message, **kwargs)
            except KeyboardInterrupt:
                break
