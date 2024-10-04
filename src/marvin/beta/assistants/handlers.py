from openai import AsyncAssistantEventHandler
from openai.types.beta.threads import Message, MessageDelta
from openai.types.beta.threads.runs import RunStep, RunStepDelta
from rich.console import Group
from rich.live import Live
from typing_extensions import override

from marvin.beta.assistants.formatting import format_run
from marvin.extensions.memory.runtime_memory import RuntimeMemory
from marvin.extensions.utilities.dispatch import Dispatcher


class PrintHandler(AsyncAssistantEventHandler):
    def __init__(self, print_messages: bool = True, print_steps: bool = True, **kwargs):
        self.print_messages = print_messages
        self.print_steps = print_steps
        self.live = Live(refresh_per_second=12)
        self.live.start()
        self.messages = {}
        self.steps = {}
        super().__init__()

        self.tool_calls = []

        # the original context dict.
        ctx = kwargs.get("context")
        self.context = ctx
        if ctx:
            self._context = ctx.context_dict
        self.memory = kwargs.get("memory") or RuntimeMemory()
        self.cache = kwargs.get("cache") or {}
        self.dispatcher = Dispatcher(context=self.context)
        self.status_stack = []
        self.previous_event = None
        self.processed_steps = []
        self.max_runs = 20
        self.openai_run_id = None
        self.openai_thread_id = kwargs.get("openai_thread_id")
        self.openai_assistant_id = kwargs.get("openai_assistant_id")
        self.persist_data = kwargs.get("persist_data", True)
        self.tool_outputs = []

    def print_run(self):
        class Run:
            messages = self.messages.values()
            steps = self.steps.values()

        panels = format_run(
            Run,
            include_messages=self.print_messages,
            include_steps=self.print_steps,
        )
        self.live.update(Group(*panels))

    @override
    async def on_message_delta(self, delta: MessageDelta, snapshot: Message) -> None:
        self.messages[snapshot.id] = snapshot
        self.print_run()

    @override
    async def on_message_done(self, message: Message) -> None:
        self.messages[message.id] = message
        self.print_run()

    @override
    async def on_run_step_delta(self, delta: RunStepDelta, snapshot: RunStep) -> None:
        self.steps[snapshot.id] = snapshot
        self.print_run()

    @override
    async def on_run_step_done(self, run_step: RunStep) -> None:
        self.steps[run_step.id] = run_step
        self.print_run()

    @override
    async def on_exception(self, exc):
        self.live.stop()

    @override
    async def on_end(self):
        self.live.stop()
