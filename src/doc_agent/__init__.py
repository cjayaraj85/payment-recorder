"""A small documentation agent with structured tool metadata."""

from .agent import DocumentationAgent
from .executor import ToolExecutionError, ToolExecutor
from .tools import ToolContext, build_tool_registry

__all__ = [
    "DocumentationAgent",
    "ToolContext",
    "ToolExecutionError",
    "ToolExecutor",
    "build_tool_registry",
]

