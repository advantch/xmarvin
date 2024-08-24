import asyncio
import threading
import traceback
from typing import TypeVar

import rich
from asgiref.local import Local
from django_eventstream import send_event

T = TypeVar("T")

BACKGROUND_TASKS = set()
STREAMING_TASKS: dict[str, asyncio.Task] = {}


def check_event_loop():
    try:
        asyncio.get_running_loop()
        #
        return True
    except RuntimeError:
        return False


def get_thread_state():
    """Return a thread-local state object."""
    if check_event_loop():
        state = Local()
    else:
        state = threading.local()
    return state


def save_task(task: asyncio.Task[T], task_id) -> None:
    """Save the task to cache"""
    BACKGROUND_TASKS.add(task)
    STREAMING_TASKS[task_id] = task


def remove_task(task_id: str) -> None:
    """Remove the task from cache"""
    if task_id in STREAMING_TASKS:
        del STREAMING_TASKS[task_id]


def get_task(task_id: str) -> asyncio.Task[T]:
    """Get the task from cache"""
    return STREAMING_TASKS.get(task_id, None)


def task_cache():
    # return django_cache
    return BACKGROUND_TASKS


def completed_task_exceptions(task, run_id, request, data, cache=None):
    if task.cancelled():
        # handler for cancelled task
        rich.print(f"[bold green]Task {run_id} cancelled[/bold green]")
        rich.print(
            f"[bold green] Sending close event to {data.channel_id} "
            f"on {data.thread_id} [/bold green]"
        )
        send_event(
            str(data.channel_id),
            str(data.thread_id),
            {
                "type": "close",
                "event": "close_current_stream",
                "generationId": data.run_id,
            },
        )
        return task_cache().discard(task)

    exception = task.exception()
    if exception:
        # handler for exception raised in task

        rich.print(traceback.print_tb(exception.__traceback__))
        rich.print(f"[bold red]Task {run_id} raised exception {exception}[/bold red]")
        rich.print(
            f"[bold red] Sending close event to {data.channel_id}"
            f" on {data.thread_id} [/bold red]"
        )
        send_event(
            str(data.channel_id),
            str(data.thread_id),
            {
                "type": "close",
                "event": "close_current_stream_error",
                "runId": data.run_id,
                "errorDetail": str(task.exception()),
                "error": "Something went wrong, please try again later.",
            },
        )
        return task_cache().discard(task)

    else:
        rich.print(f"[bold green]Task {run_id} completed success [/bold green]")
        rich.print(
            f"[bold green] Sending close event to {data.channel_id} "
            f"on {data.thread_id} [/bold green]"
        )
        send_event(
            str(data.channel_id),
            str(data.thread_id),
            {
                "type": "close",
                "event": "close_current_stream",
                "runId": data.run_id,
            },
        )
        task_cache().discard(task)
