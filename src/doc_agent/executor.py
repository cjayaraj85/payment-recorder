"""Validation and execution layer for agent tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

from .tools import Tool


class ToolExecutionError(ValueError):
    """Raised when a tool call is invalid or cannot be executed."""

    pass


@dataclass(frozen=True)
class ToolCallResult:
    """Result captured after one tool call executes."""

    tool_name: str
    args: Dict[str, Any]
    result: Any


class ToolExecutor:
    """Executes tool actions after validating their JSON-style arguments."""

    def __init__(self, tools: Mapping[str, Tool]):
        self.tools = dict(tools)

    def metadata(self) -> list[Dict[str, Any]]:
        """Return all tool metadata in the shape shown to the agent."""
        return [tool.metadata() for tool in self.tools.values()]

    def execute(self, action: Mapping[str, Any]) -> ToolCallResult:
        """Validate and execute an action containing tool_name and args."""
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
        result = tool.handler(args)
        return ToolCallResult(tool_name=tool_name, args=dict(args), result=result)


def validate_args(tool: Tool, args: Mapping[str, Any]) -> None:
    """Validate tool arguments against the subset of JSON Schema used here."""
    schema = tool.parameters
    if schema.get("type") != "object":
        raise ToolExecutionError(f"Tool {tool.name} must define object parameters.")

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
        if expected == "integer" and not isinstance(value, int):
            raise ToolExecutionError(f"Tool {tool.name} arg {name} must be an integer.")
        if expected == "boolean" and not isinstance(value, bool):
            raise ToolExecutionError(f"Tool {tool.name} arg {name} must be a boolean.")
