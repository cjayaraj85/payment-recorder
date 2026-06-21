"""Command-line entry point for the function-calling agent demo."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from .agent import FunctionCallingAgent


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Prompt for one action and print the selected tool result."""
    _ = list(argv) if argv is not None else None
    agent = FunctionCallingAgent(Path.cwd())
    request = input("What action should the agent take? ")
    response = agent.run(request)
    print(response.format())
    return 0

