"""Python functions exposed as structured tools for an interactive agent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping


JSONSchema = Dict[str, Any]
ToolHandler = Callable[[Mapping[str, Any]], Any]


class ToolExecutionError(ValueError):
    """Raised when a tool call is invalid or unsafe."""


@dataclass(frozen=True)
class Tool:
    """Python function plus metadata that describes how an agent should call it."""

    name: str
    description: str
    parameters: JSONSchema
    handler: ToolHandler

    def metadata(self) -> Dict[str, Any]:
        """Return tool metadata in the agent-facing JSON shape."""
        return {
            "tool_name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass(frozen=True)
class ToolContext:
    """Filesystem context used by the local demo tools."""

    root: Path

    @property
    def safe_root(self) -> Path:
        return self.root.resolve()


@dataclass(frozen=True)
class ToolCallResult:
    """Result from one executed tool call."""

    tool_name: str
    args: Dict[str, Any]
    result: Any


class ToolExecutor:
    """Validates JSON-like tool calls and invokes Python functions."""

    def __init__(self, tools: Mapping[str, Tool]):
        self.tools = dict(tools)

    def metadata(self) -> list[Dict[str, Any]]:
        """Return metadata for every registered tool."""
        return [tool.metadata() for tool in self.tools.values()]

    def execute(self, action: Mapping[str, Any]) -> ToolCallResult:
        """Execute an action shaped as {'tool_name': str, 'args': object}."""
        tool_name = action.get("tool_name")
        args = action.get("args", {})

        if not isinstance(tool_name, str) or not tool_name:
            raise ToolExecutionError("Tool action must include a non-empty tool_name.")
        if tool_name not in self.tools:
            raise ToolExecutionError(f"Unknown tool: {tool_name}")
        if not isinstance(args, dict):
            raise ToolExecutionError("Tool action args must be an object.")

        tool = self.tools[tool_name]
        validate_args(tool, args)
        return ToolCallResult(
            tool_name=tool_name,
            args=dict(args),
            result=tool.handler(args),
        )


def build_tool_registry(context: ToolContext) -> Dict[str, Tool]:
    """Build the tools available to the interactive function-calling agent."""
    return {
        "list_directory": Tool(
            name="list_directory",
            description="Lists files and directories at a path under the workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list. Use '.' for the current directory.",
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=lambda args: list_directory(context, str(args["path"])),
        ),
        "read_text_file": Tool(
            name="read_text_file",
            description="Reads a UTF-8 text file under the workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path to read, relative to the workspace.",
                    },
                },
                "required": ["file_path"],
                "additionalProperties": False,
            },
            handler=lambda args: read_text_file(context, str(args["file_path"])),
        ),
        "get_current_directory": Tool(
            name="get_current_directory",
            description="Returns the workspace directory used by this agent.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            handler=lambda args: context.safe_root.as_posix(),
        ),
    }


def list_directory(context: ToolContext, path: str) -> list[str]:
    """List directory entries under the safe workspace root."""
    directory = resolve_under_root(context, path)
    if not directory.exists():
        raise ToolExecutionError(f"Directory does not exist: {path}")
    if not directory.is_dir():
        raise ToolExecutionError(f"Path is not a directory: {path}")

    entries = []
    for child in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
        suffix = "/" if child.is_dir() else ""
        entries.append(child.name + suffix)
    return entries


def read_text_file(context: ToolContext, file_path: str) -> str:
    """Read a text file under the safe workspace root."""
    path = resolve_under_root(context, file_path)
    if not path.exists():
        raise ToolExecutionError(f"File does not exist: {file_path}")
    if not path.is_file():
        raise ToolExecutionError(f"Path is not a file: {file_path}")
    return path.read_text(encoding="utf-8")


def resolve_under_root(context: ToolContext, path: str) -> Path:
    """Resolve a relative path and reject paths outside the safe root."""
    candidate = Path(path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (context.safe_root / candidate).resolve()

    try:
        resolved.relative_to(context.safe_root)
    except ValueError as exc:
        raise ToolExecutionError("Tool access outside the workspace is not allowed.") from exc
    return resolved


def validate_args(tool: Tool, args: Mapping[str, Any]) -> None:
    """Validate action args against the small JSON Schema subset used here."""
    schema = tool.parameters
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    for name in required:
        if name not in args:
            raise ToolExecutionError(f"Tool {tool.name} missing required arg: {name}")

    if schema.get("additionalProperties") is False:
        extra = sorted(set(args.keys()) - set(properties.keys()))
        if extra:
            raise ToolExecutionError(
                f"Tool {tool.name} received unknown arg(s): {', '.join(extra)}"
            )

    for name, value in args.items():
        expected = properties.get(name, {}).get("type")
        if expected == "string" and not isinstance(value, str):
            raise ToolExecutionError(f"Tool {tool.name} arg {name} must be a string.")

