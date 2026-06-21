"""Command-line entry point for the LLM function-calling demo."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional

from .llm_agent import LLMFunctionCallingAgent


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Prompt for a task and run the LLM function-calling agent loop."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    agent = LLMFunctionCallingAgent(root=Path(args.root), model=args.model)
    user_task = input("What would you like me to do? ")
    try:
        response = agent.run_loop(user_task, max_iterations=args.max_iterations)
    except Exception as exc:
        print(f"LLM function-calling request failed: {type(exc).__name__}: {exc}")
        return 1
    print(response.format())
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments for the LLM function-calling demo."""
    parser = argparse.ArgumentParser(
        prog="llm-function-agent",
        description="Use LLM function calling to select and execute Python tools.",
    )
    parser.add_argument(
        "--model",
        default="openai/gpt-4o",
        help="LiteLLM model name. Defaults to openai/gpt-4o.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Workspace root for file tools. Defaults to current directory.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of model/tool loop iterations. Defaults to 10.",
    )
    return parser
