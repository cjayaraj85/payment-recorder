"""Natural-language toy agent that chooses and calls Python functions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Dict, Optional

from .tools import ToolCallResult, ToolContext, ToolExecutor, build_tool_registry


@dataclass(frozen=True)
class AgentResponse:
    """Response returned after the agent decides whether to call a tool."""

    request: str
    message: str
    action: Optional[Dict[str, Any]] = None
    tool_result: Optional[ToolCallResult] = None

    def format(self) -> str:
        """Render the response for notebook or terminal display."""
        lines = [self.message]
        if self.action:
            lines.extend(["", f"Tool choice: {self.action}"])
        if self.tool_result:
            lines.extend(["", "Tool result:", format_result(self.tool_result.result)])
        return "\n".join(lines)


class FunctionCallingAgent:
    """Small demo agent that maps simple requests to structured tool calls."""

    def __init__(self, root: Optional[Path] = None):
        context = ToolContext(root=(root or Path.cwd()).resolve())
        self.executor = ToolExecutor(build_tool_registry(context))

    def describe_tools(self) -> list[Dict[str, Any]]:
        """Return metadata for tools available to the agent."""
        return self.executor.metadata()

    def run(self, request: str) -> AgentResponse:
        """Choose a tool for a natural-language request and execute it."""
        action = choose_action(request)
        if action is None:
            return AgentResponse(
                request=request,
                message=(
                    "I do not have a safe tool for that request. Try asking me to "
                    "list a directory, show the current directory, or read a text file."
                ),
            )

        result = self.executor.execute(action)
        return AgentResponse(
            request=request,
            message=f"I selected `{result.tool_name}` for this request.",
            action=action,
            tool_result=result,
        )


def choose_action(request: str) -> Optional[Dict[str, Any]]:
    """Choose a structured tool call from a simple natural-language request."""
    normalized = request.strip().lower()

    if not normalized:
        return None

    if mentions_current_directory(normalized):
        if any(word in normalized for word in ["where", "path", "pwd", "location"]):
            return {"tool_name": "get_current_directory", "args": {}}
        return {"tool_name": "list_directory", "args": {"path": "."}}

    if any(word in normalized for word in ["list", "show", "tell me"]) and any(
        word in normalized for word in ["files", "directory", "folder", "dir"]
    ):
        return {"tool_name": "list_directory", "args": {"path": extract_path(request) or "."}}

    if any(word in normalized for word in ["read", "open", "show"]) and any(
        word in normalized for word in ["file", ".py", ".md", ".txt", ".json"]
    ):
        file_path = extract_path(request)
        if file_path:
            return {"tool_name": "read_text_file", "args": {"file_path": file_path}}

    return None


def mentions_current_directory(normalized_request: str) -> bool:
    """Return whether a request refers to the current directory."""
    phrases = [
        "current directory",
        "current folder",
        "this directory",
        "this folder",
        "cwd",
        "working directory",
    ]
    return any(phrase in normalized_request for phrase in phrases)


def extract_path(request: str) -> Optional[str]:
    """Extract a likely file or directory path from a natural-language request."""
    quoted = re.search(r"['\"]([^'\"]+)['\"]", request)
    if quoted:
        return quoted.group(1)

    tokens = request.strip().split()
    for token in reversed(tokens):
        cleaned = token.strip(".,:;!?")
        if "/" in cleaned or "." in cleaned:
            return cleaned
    return None


def format_result(result: Any) -> str:
    """Render tool output as readable text."""
    if isinstance(result, list):
        return "\n".join(f"- {item}" for item in result)
    return str(result)

