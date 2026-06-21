"""LLM function-calling agent that executes Python tools from model tool calls."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from .tools import ToolContext, ToolExecutionError, list_directory, read_text_file


CompletionFunction = Callable[..., Any]


AGENT_RULES = [
    {
        "role": "system",
        "content": (
            "You are an AI agent that can perform tasks by using available tools. "
            "If a user asks about files, documents, or content, first list the files "
            "before reading them. When you are done, terminate the conversation by "
            'using the "terminate" tool with a short summary message.'
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
    {
        "type": "function",
        "function": {
            "name": "terminate",
            "description": (
                "Terminates the conversation after the task is complete. "
                "No further actions are possible after this call."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Final summary message for the user.",
                    },
                },
                "required": ["message"],
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


@dataclass(frozen=True)
class LLMAgentLoopStep:
    """One function-calling iteration from the simplified agent loop."""

    iteration: int
    tool_name: Optional[str]
    tool_args: Dict[str, Any]
    result: Dict[str, Any]

    @property
    def error(self) -> Optional[str]:
        """Return the tool error message when this step failed."""
        value = self.result.get("error")
        return str(value) if value is not None else None


@dataclass(frozen=True)
class LLMAgentLoopResult:
    """Result from a multi-step function-calling agent loop."""

    user_task: str
    messages: List[Dict[str, str]]
    steps: List[LLMAgentLoopStep]
    final_message: str
    stopped_reason: str

    @property
    def terminated(self) -> bool:
        """Return whether the loop stopped through the terminate tool."""
        return self.stopped_reason == "terminated"

    def format(self) -> str:
        """Render the loop trace and final answer in notebook-friendly text."""
        lines: List[str] = []
        for step in self.steps:
            lines.extend(
                [
                    f"Iteration {step.iteration}",
                    f"Tool Name: {step.tool_name}",
                    f"Tool Arguments: {step.tool_args}",
                    "Result:",
                    format_result(step.result),
                    "",
                ]
            )
        lines.append(f"Final: {self.final_message}")
        lines.append(f"Stopped Reason: {self.stopped_reason}")
        return "\n".join(lines)


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
            "terminate": self.terminate,
        }

    def list_files(self) -> List[str]:
        """List files in the workspace root."""
        return list_directory(self.context, ".")

    def read_file(self, file_name: str) -> str:
        """Read a UTF-8 text file from the workspace."""
        return read_text_file(self.context, file_name)

    def terminate(self, message: str) -> str:
        """Return the final summary message for a completed agent loop."""
        return message

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

    def run_loop(self, user_task: str, max_iterations: int = 10) -> LLMAgentLoopResult:
        """Run a simplified function-calling agent loop until termination."""
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1.")

        memory = [{"role": "user", "content": user_task}]
        steps: List[LLMAgentLoopStep] = []

        for iteration in range(1, max_iterations + 1):
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
                final_message = model_content or "The model returned no tool call or text."
                return LLMAgentLoopResult(
                    user_task=user_task,
                    messages=AGENT_RULES + memory,
                    steps=steps,
                    final_message=final_message,
                    stopped_reason="model_response",
                )

            action, result = self.execute_tool_call(tool_calls[0])
            step = LLMAgentLoopStep(
                iteration=iteration,
                tool_name=action.get("tool_name"),
                tool_args=action.get("args", {}),
                result=result,
            )
            steps.append(step)

            if step.tool_name == "terminate" and step.error is None:
                final_message = str(result.get("result", ""))
                memory.append({"role": "assistant", "content": json.dumps(action)})
                return LLMAgentLoopResult(
                    user_task=user_task,
                    messages=AGENT_RULES + memory,
                    steps=steps,
                    final_message=final_message,
                    stopped_reason="terminated",
                )

            memory.extend(
                [
                    {"role": "assistant", "content": json.dumps(action)},
                    {"role": "user", "content": json.dumps(result, default=str)},
                ]
            )

        return LLMAgentLoopResult(
            user_task=user_task,
            messages=AGENT_RULES + memory,
            steps=steps,
            final_message=f"Stopped after reaching {max_iterations} iterations.",
            stopped_reason="max_iterations",
        )

    def execute_tool_call(self, tool_call: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Parse and execute one model-selected tool call."""
        function_call = get_value(tool_call, "function")
        tool_name = get_value(function_call, "name")
        if not isinstance(tool_name, str) or not tool_name:
            action = {"tool_name": None, "args": {}}
            return action, {"error": "Tool call did not include a valid function name."}

        try:
            tool_args = parse_tool_arguments(get_value(function_call, "arguments"))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            action = {"tool_name": tool_name, "args": {}}
            return action, {
                "error": f"Invalid arguments for {tool_name}: {exc}",
            }

        action = {"tool_name": tool_name, "args": tool_args}
        try:
            return action, {"result": self.execute_tool(tool_name, tool_args)}
        except Exception as exc:
            return action, {"error": f"Error executing {tool_name}: {exc}"}

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
    if isinstance(result, dict):
        return json.dumps(result, indent=2, default=str)
    return str(result)
