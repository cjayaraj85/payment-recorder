"""Tool definitions and handlers for the documentation agent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping


JSONSchema = Dict[str, Any]
ToolHandler = Callable[[Mapping[str, Any]], Any]


@dataclass(frozen=True)
class Tool:
    """Executable tool with metadata the agent can inspect."""

    name: str
    description: str
    parameters: JSONSchema
    handler: ToolHandler

    def metadata(self) -> Dict[str, Any]:
        """Return the agent-facing tool description."""
        return {
            "tool_name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass(frozen=True)
class ToolContext:
    """Project paths used by the file operation tools."""

    project_root: Path
    src_dir: str = "src"
    docs_dir: str = "docs"

    @property
    def source_root(self) -> Path:
        return (self.project_root / self.src_dir).resolve()

    @property
    def documentation_root(self) -> Path:
        return (self.project_root / self.docs_dir).resolve()


def build_tool_registry(context: ToolContext) -> Dict[str, Tool]:
    """Build the complete tool registry available to the agent."""
    return {
        "list_python_files": Tool(
            name="list_python_files",
            description="Returns a list of all Python files in the configured src directory.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            handler=lambda args: list_python_files(context),
        ),
        "read_file": Tool(
            name="read_file",
            description="Reads the content of a specified Python source file.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to a Python file inside the configured src directory.",
                    },
                },
                "required": ["file_path"],
                "additionalProperties": False,
            },
            handler=lambda args: read_file(context, str(args["file_path"])),
        ),
        "write_doc_file": Tool(
            name="write_doc_file",
            description="Writes a documentation file to the configured docs directory.",
            parameters={
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "Documentation file name relative to the docs directory.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown documentation content to write.",
                    },
                },
                "required": ["file_name", "content"],
                "additionalProperties": False,
            },
            handler=lambda args: write_doc_file(
                context,
                str(args["file_name"]),
                str(args["content"]),
            ),
        ),
        "list_doc_files": Tool(
            name="list_doc_files",
            description="Returns a list of Markdown documentation files in the configured docs directory.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            handler=lambda args: list_doc_files(context),
        ),
        "read_doc_file": Tool(
            name="read_doc_file",
            description="Reads the content of a specified Markdown documentation file.",
            parameters={
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "Documentation file name relative to the docs directory.",
                    },
                },
                "required": ["file_name"],
                "additionalProperties": False,
            },
            handler=lambda args: read_doc_file(context, str(args["file_name"])),
        ),
        "delete_doc_file": Tool(
            name="delete_doc_file",
            description="Deletes a stale generated Markdown documentation file from the configured docs directory.",
            parameters={
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "Documentation file name relative to the docs directory.",
                    },
                },
                "required": ["file_name"],
                "additionalProperties": False,
            },
            handler=lambda args: delete_doc_file(context, str(args["file_name"])),
        ),
    }


def list_python_files(context: ToolContext) -> list[str]:
    """Return Python files under the configured source directory."""
    source_root = context.source_root
    if not source_root.exists():
        return []

    files = []
    for path in sorted(source_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        files.append(relative_to_root(context.project_root, path))
    return files


def read_file(context: ToolContext, file_path: str) -> str:
    """Read a Python source file after validating its location."""
    path = resolve_under_root(context.project_root, file_path)
    if not is_relative_to(path, context.source_root):
        raise ValueError(f"read_file can only read files in {context.src_dir}/")
    if path.suffix != ".py":
        raise ValueError("read_file can only read Python files.")
    return path.read_text(encoding="utf-8")


def write_doc_file(context: ToolContext, file_name: str, content: str) -> str:
    """Write Markdown documentation under the configured docs directory."""
    path = resolve_doc_file(context, file_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return relative_to_root(context.project_root, path)


def list_doc_files(context: ToolContext) -> list[str]:
    """Return Markdown files under the configured documentation directory."""
    docs_root = context.documentation_root
    if not docs_root.exists():
        return []

    files = []
    for path in sorted(docs_root.rglob("*.md")):
        if "__pycache__" in path.parts:
            continue
        files.append(relative_to_root(docs_root, path))
    return files


def read_doc_file(context: ToolContext, file_name: str) -> str:
    """Read a Markdown documentation file after validating its location."""
    path = resolve_doc_file(context, file_name)
    return path.read_text(encoding="utf-8")


def delete_doc_file(context: ToolContext, file_name: str) -> str:
    """Delete a Markdown documentation file after validating its location."""
    path = resolve_doc_file(context, file_name)
    path.unlink()
    remove_empty_parent_dirs(path.parent, context.documentation_root)
    return relative_to_root(context.project_root, path)


def resolve_doc_file(context: ToolContext, file_name: str) -> Path:
    """Resolve and validate a docs-relative Markdown file path."""
    docs_root = context.documentation_root
    path = resolve_under_root(docs_root, file_name)
    if not is_relative_to(path, docs_root):
        raise ValueError(f"Documentation tools can only access {context.docs_dir}/")
    if path.suffix != ".md":
        raise ValueError("Documentation tools can only access Markdown files.")
    return path


def remove_empty_parent_dirs(path: Path, stop_at: Path) -> None:
    """Remove empty directories above a deleted docs file."""
    stop_at = stop_at.resolve()
    current = path.resolve()
    while current != stop_at and is_relative_to(current, stop_at):
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def resolve_under_root(root: Path, path: str) -> Path:
    """Resolve an absolute or relative path from a trusted root."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (root / candidate).resolve()


def relative_to_root(root: Path, path: Path) -> str:
    """Return a POSIX path for a file relative to the project root."""
    return path.resolve().relative_to(root.resolve()).as_posix()


def is_relative_to(path: Path, root: Path) -> bool:
    """Return whether a path is contained within a root directory."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
