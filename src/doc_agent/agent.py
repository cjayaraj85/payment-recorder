"""Agent orchestration for source scanning and documentation writing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Dict, List

from .docgen import (
    documentation_file_name,
    generate_markdown_documentation,
    is_generated_document,
)
from .executor import ToolCallResult, ToolExecutor


@dataclass(frozen=True)
class AgentRunResult:
    """Summary of one documentation agent run."""

    files_documented: int
    source_files_found: int
    docs_written: List[str]
    docs_unchanged: List[str]
    outdated_docs: List[str]
    stale_docs: List[str]
    stale_docs_deleted: List[str]
    tool_calls: List[ToolCallResult]

    @property
    def has_pending_changes(self) -> bool:
        """Return whether generated docs are missing, stale, or out of date."""
        return bool(self.outdated_docs or self.stale_docs)


class DocumentationAgent:
    """Agent that uses structured file tools to generate Markdown docs."""

    def __init__(
        self,
        executor: ToolExecutor,
        src_dir: str = "src",
        docs_dir: str = "docs",
    ):
        self.executor = executor
        self.src_dir = src_dir
        self.docs_dir = docs_dir

    def run(
        self,
        incremental: bool = False,
        prune_stale: bool = False,
        check: bool = False,
    ) -> AgentRunResult:
        """Generate, check, or prune docs for Python files returned by the tools."""
        tool_calls: List[ToolCallResult] = []
        docs_written: List[str] = []
        docs_unchanged: List[str] = []
        outdated_docs: List[str] = []
        stale_docs_deleted: List[str] = []

        list_result = self._execute(
            {"tool_name": "list_python_files", "args": {}},
            tool_calls,
        )
        python_files = list_result.result
        existing_docs = self._load_existing_docs(tool_calls)
        expected_doc_names = {
            documentation_file_name(file_path, self.src_dir)
            for file_path in python_files
        }

        for file_path in python_files:
            read_result = self._execute(
                {
                    "tool_name": "read_file",
                    "args": {"file_path": file_path},
                },
                tool_calls,
            )
            documentation = generate_markdown_documentation(file_path, read_result.result)
            doc_name = documentation_file_name(file_path, self.src_dir)
            project_doc_path = self._project_doc_path(doc_name)
            existing_content = existing_docs.get(doc_name)
            needs_update = existing_content != documentation

            if needs_update:
                outdated_docs.append(project_doc_path)
            else:
                docs_unchanged.append(project_doc_path)

            if check:
                continue

            if not incremental or needs_update:
                write_result = self._execute(
                    {
                        "tool_name": "write_doc_file",
                        "args": {
                            "file_name": doc_name,
                            "content": documentation,
                        },
                    },
                    tool_calls,
                )
                docs_written.append(write_result.result)

        stale_doc_names = self._stale_generated_docs(existing_docs, expected_doc_names)
        stale_docs = [self._project_doc_path(doc_name) for doc_name in stale_doc_names]

        if prune_stale and not check:
            for doc_name in stale_doc_names:
                delete_result = self._execute(
                    {
                        "tool_name": "delete_doc_file",
                        "args": {"file_name": doc_name},
                    },
                    tool_calls,
                )
                stale_docs_deleted.append(delete_result.result)
            stale_docs = []

        return AgentRunResult(
            files_documented=len(docs_written),
            source_files_found=len(python_files),
            docs_written=docs_written,
            docs_unchanged=docs_unchanged,
            outdated_docs=outdated_docs,
            stale_docs=stale_docs,
            stale_docs_deleted=stale_docs_deleted,
            tool_calls=tool_calls,
        )

    def _load_existing_docs(self, tool_calls: List[ToolCallResult]) -> Dict[str, str]:
        list_docs_result = self._execute(
            {"tool_name": "list_doc_files", "args": {}},
            tool_calls,
        )
        docs: Dict[str, str] = {}
        for doc_name in list_docs_result.result:
            read_doc_result = self._execute(
                {
                    "tool_name": "read_doc_file",
                    "args": {"file_name": doc_name},
                },
                tool_calls,
            )
            docs[doc_name] = read_doc_result.result
        return docs

    def _stale_generated_docs(
        self,
        existing_docs: Dict[str, str],
        expected_doc_names: set[str],
    ) -> List[str]:
        stale_docs = []
        for doc_name, content in existing_docs.items():
            if doc_name not in expected_doc_names and is_generated_document(content):
                stale_docs.append(doc_name)
        return sorted(stale_docs)

    def _project_doc_path(self, doc_name: str) -> str:
        return (PurePosixPath(self.docs_dir) / doc_name).as_posix()

    def _execute(
        self,
        action: Dict[str, Any],
        tool_calls: List[ToolCallResult],
    ) -> ToolCallResult:
        result = self.executor.execute(action)
        tool_calls.append(result)
        return result
