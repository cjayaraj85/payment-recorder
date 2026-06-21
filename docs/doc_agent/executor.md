# `doc_agent.executor`

Source: `src/doc_agent/executor.py`

## Summary

Validation and execution layer for agent tool calls.

## Classes

### `ToolExecutionError`

Raised when a tool call is invalid or cannot be executed.

Methods: none.

### `ToolCallResult`

Result captured after one tool call executes.

Methods: none.

### `ToolExecutor`

Executes tool actions after validating their JSON-style arguments.

Methods:

- `__init__(self, tools: Mapping[str, Tool])`
- `metadata(self) -> list[Dict[str, Any]]`
- `execute(self, action: Mapping[str, Any]) -> ToolCallResult`

## Functions

### `validate_args(tool: Tool, args: Mapping[str, Any]) -> None`

Validate tool arguments against the subset of JSON Schema used here.
