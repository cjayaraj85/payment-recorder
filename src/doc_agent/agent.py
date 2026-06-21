"""Agent orchestration for source scanning and documentation writing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .docgen import documentation_file_name, generate_markdown_documentation
from .executor import ToolCallResult, ToolExecutor


@dataclass(frozen=True)
class AgentRunResult:
    """Summary of one documentation agent run."""

    files_documented: int
    docs_written: List[str]
    tool_calls: List[ToolCallResult]


class DocumentationAgent:
    """Agent that uses structured file tools to generate Markdown docs."""

    def __init__(self, executor: ToolExecutor, src_dir: str = "src"):
        self.executor = executor
        self.src_dir = src_dir

    def run(self) -> AgentRunResult:
        """Run the agent over every Python file returned by list_python_files."""
        tool_calls: List[ToolCallResult] = []
        docs_written: List[str] = []

        list_result = self._execute(
            {"tool_name": "list_python_files", "args": {}},
            tool_calls,
        )
        python_files = list_result.result

        for file_path in python_files:
            read_result = self._execute(
                {
                    "tool_name": "read_file",
                    "args": {"file_path": file_path},
                },
                tool_calls,
            )
            documentation = generate_markdown_documentation(file_path, read_result.result)
            write_result = self._execute(
                {
                    "tool_name": "write_doc_file",
                    "args": {
                        "file_name": documentation_file_name(file_path, self.src_dir),
                        "content": documentation,
                    },
                },
                tool_calls,
            )
            docs_written.append(write_result.result)

        return AgentRunResult(
            files_documented=len(python_files),
            docs_written=docs_written,
            tool_calls=tool_calls,
        )

    def _execute(
        self,
        action: Dict[str, Any],
        tool_calls: List[ToolCallResult],
    ) -> ToolCallResult:
        result = self.executor.execute(action)
        tool_calls.append(result)
        return result
