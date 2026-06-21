"""Command-line interface for the documentation agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Optional

from .agent import AgentRunResult, DocumentationAgent
from .executor import ToolExecutor
from .tools import ToolContext, build_tool_registry


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Run the documentation agent CLI."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    context = ToolContext(
        project_root=Path(args.project_root).resolve(),
        src_dir=args.src_dir,
        docs_dir=args.docs_dir,
    )
    executor = ToolExecutor(build_tool_registry(context))

    if args.command == "tools":
        print(json.dumps(executor.metadata(), indent=2))
        return 0

    if args.command == "run":
        result = DocumentationAgent(
            executor,
            src_dir=args.src_dir,
            docs_dir=args.docs_dir,
        ).run(
            incremental=args.incremental,
            prune_stale=args.prune_stale,
            check=args.check,
        )
        if args.check:
            return report_check_result(result)

        print(f"Found {result.source_files_found} Python file(s).")
        if result.docs_written:
            for doc_path in result.docs_written:
                print(f"Wrote {doc_path}")
        else:
            print("No documentation files needed updates.")
        for doc_path in result.stale_docs_deleted:
            print(f"Deleted stale {doc_path}")
        if result.stale_docs:
            print("Stale generated docs remain:")
            for doc_path in result.stale_docs:
                print(f"  {doc_path}")
            print("Run with --prune-stale to delete them.")
        if args.show_trace:
            print("\nTool calls:")
            for call in result.tool_calls:
                print(json.dumps({"tool_name": call.tool_name, "args": call.args}))
        return 0

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    """Build the doc-agent argument parser."""
    parser = argparse.ArgumentParser(
        prog="doc-agent",
        description="Generate Markdown docs by using structured AI-agent tool metadata.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory. Defaults to the current directory.",
    )
    parser.add_argument(
        "--src-dir",
        default="src",
        help="Source directory to scan. Defaults to src.",
    )
    parser.add_argument(
        "--docs-dir",
        default="docs",
        help="Documentation directory to write. Defaults to docs.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("tools", help="Print tool metadata as JSON.")

    run_parser = subparsers.add_parser("run", help="Generate documentation.")
    run_parser.add_argument(
        "--incremental",
        action="store_true",
        help="Write only missing or changed generated docs.",
    )
    run_parser.add_argument(
        "--prune-stale",
        action="store_true",
        help="Delete stale generated docs whose source files no longer exist.",
    )
    run_parser.add_argument(
        "--check",
        action="store_true",
        help="Fail without writing files when generated docs are out of date.",
    )
    run_parser.add_argument(
        "--show-trace",
        action="store_true",
        help="Print the tool calls selected by the agent.",
    )
    return parser


def report_check_result(result: AgentRunResult) -> int:
    """Print a documentation freshness report and return a process status."""
    if not result.has_pending_changes:
        print("Documentation is up to date.")
        return 0

    print("Documentation is out of date.")
    if result.outdated_docs:
        print("Missing or outdated docs:")
        for doc_path in result.outdated_docs:
            print(f"  {doc_path}")
    if result.stale_docs:
        print("Stale generated docs:")
        for doc_path in result.stale_docs:
            print(f"  {doc_path}")
    print("Run: python3 doc_agent.py run --incremental --prune-stale")
    return 1
