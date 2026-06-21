"""LLM function-calling agent that executes Python tools from model tool calls."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

from .tools import ToolContext, ToolExecutionError, list_directory, read_text_file


CompletionFunction = Callable[..., Any]


AGENT_RULES = [
    {
        "role": "system",
        "content": (
            "You are an AI agent that can perform tasks by using available tools. "
            "If a user asks about files, documents, or content, first list the files "
            "before reading them."
        ),
    }
]


LLM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Returns a list of files in the current workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the content of a specified file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "File name or relative path to read.",
                    },
                },
                "required": ["file_name"],
                "additionalProperties": False,
            },
        },
    },
]


@dataclass(frozen=True)
class LLMFunctionCallResult:
    """Result from one LLM function-calling turn."""

    user_task: str
    messages: List[Dict[str, str]]
    model_content: Optional[str]
    tool_name: Optional[str]
    tool_args: Dict[str, Any]
    result: Any

    @property
    def called_tool(self) -> bool:
        """Return whether the model selected a function tool."""
        return self.tool_name is not None

    def format(self) -> str:
        """Render the LLM turn and tool execution in notebook-friendly text."""
        if not self.called_tool:
            return self.model_content or "The model returned no tool call or text."

        return "\n".join(
            [
                f"Tool Name: {self.tool_name}",
                f"Tool Arguments: {self.tool_args}",
                "Result:",
                format_result(self.result),
            ]
        )


class LLMFunctionCallingAgent:
    """Agent that delegates tool choice to an LLM function-calling API."""

    def __init__(
        self,
        root: Optional[Path] = None,
        model: str = "openai/gpt-4o",
        completion_fn: Optional[CompletionFunction] = None,
    ):
        self.context = ToolContext(root=(root or Path.cwd()).resolve())
        self.model = model
        self.completion_fn = completion_fn or litellm_completion
        self.tool_functions = {
            "list_files": self.list_files,
            "read_file": self.read_file,
        }

    def list_files(self) -> List[str]:
        """List files in the workspace root."""
        return list_directory(self.context, ".")

    def read_file(self, file_name: str) -> str:
        """Read a UTF-8 text file from the workspace."""
        return read_text_file(self.context, file_name)

    def tools(self) -> List[Dict[str, Any]]:
        """Return OpenAI/LiteLLM-style function tool definitions."""
        return LLM_TOOLS

    def run(self, user_task: str) -> LLMFunctionCallResult:
        """Ask the model for a function call, then execute the selected function."""
        memory = [{"role": "user", "content": user_task}]
        messages = AGENT_RULES + memory
        response = self.completion_fn(
            model=self.model,
            messages=messages,
            tools=self.tools(),
            max_tokens=1024,
        )
        message = first_choice_message(response)
        tool_calls = get_value(message, "tool_calls") or []
        model_content = get_value(message, "content")

        if not tool_calls:
            return LLMFunctionCallResult(
                user_task=user_task,
                messages=messages,
                model_content=model_content,
                tool_name=None,
                tool_args={},
                result=model_content,
            )

        tool_call = tool_calls[0]
        function_call = get_value(tool_call, "function")
        tool_name = get_value(function_call, "name")
        tool_args = parse_tool_arguments(get_value(function_call, "arguments"))
        result = self.execute_tool(tool_name, tool_args)
        return LLMFunctionCallResult(
            user_task=user_task,
            messages=messages,
            model_content=model_content,
            tool_name=tool_name,
            tool_args=tool_args,
            result=result,
        )

    def execute_tool(self, tool_name: str, tool_args: Mapping[str, Any]) -> Any:
        """Look up and execute a model-selected tool function."""
        if tool_name not in self.tool_functions:
            raise ToolExecutionError(f"Unknown model-selected tool: {tool_name}")
        return self.tool_functions[tool_name](**dict(tool_args))


def litellm_completion(**kwargs: Any) -> Any:
    """Call LiteLLM completion, imported lazily so tests do not need the package."""
    try:
        from litellm import completion
    except ImportError as exc:
        raise RuntimeError(
            "litellm is required for real LLM function calling. Install it with "
            "`python3 -m pip install litellm` and set OPENAI_API_KEY."
        ) from exc
    return completion(**kwargs)


def first_choice_message(response: Any) -> Any:
    """Return the first model message from a LiteLLM/OpenAI-style response."""
    choices = get_value(response, "choices") or []
    if not choices:
        raise ValueError("LLM response did not include choices.")
    return get_value(choices[0], "message")


def parse_tool_arguments(arguments: Any) -> Dict[str, Any]:
    """Parse structured tool arguments from the model response."""
    if arguments in (None, ""):
        return {}
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        parsed = json.loads(arguments)
        if not isinstance(parsed, dict):
            raise ValueError("Tool arguments must decode to a JSON object.")
        return parsed
    raise TypeError("Tool arguments must be a JSON string or object.")


def get_value(value: Any, name: str) -> Any:
    """Read a field from either a dictionary or an SDK response object."""
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def format_result(result: Any) -> str:
    """Render a function result for display."""
    if isinstance(result, list):
        return "\n".join(f"- {item}" for item in result)
    return str(result)

