import json
import logging
from datetime import datetime
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel

from marvin.extensions.utilities.serialization import to_serializable

logger = logging.getLogger(__name__)


def format_timestamp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%l:%M:%S %p")


def create_panel(content: Any, title: str, timestamp: int, color: str):
    return Panel(
        content,
        title=f"[bold]{title}[/]",
        subtitle=f"[italic]{format_timestamp(timestamp)}[/]",
        title_align="left",
        subtitle_align="right",
        border_style=color,
        box=box.ROUNDED,
        width=100,
        expand=True,
        padding=(1, 2),
    )


def pretty_log(*args, propagate=False, **kwargs):
    """
    Color logger using rich.
    Propagate to the default logger if propagate is True.
    Only print if debug is True.
    """

    color = kwargs.pop("color", "green")
    console = Console()
    data = {
        "args": to_serializable(args),
        "kwargs": to_serializable(kwargs),
    }
    message = f"DEBUG LOG: \n {json.dumps(data, indent=4)}"
    panel = create_panel(message, "DEBUG", datetime.now().timestamp(), color)
    console.print(panel)
