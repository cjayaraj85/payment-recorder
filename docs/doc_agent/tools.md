# `doc_agent.tools`

Source: `src/doc_agent/tools.py`

## Summary

Tool definitions and handlers for the documentation agent.

## Classes

### `Tool`

Executable tool with metadata the agent can inspect.

Methods:

- `metadata(self) -> Dict[str, Any]`

### `ToolContext`

Project paths used by the file operation tools.

Methods:

- `source_root(self) -> Path`
- `documentation_root(self) -> Path`

## Functions

### `build_tool_registry(context: ToolContext) -> Dict[str, Tool]`

Build the complete tool registry available to the agent.

### `list_python_files(context: ToolContext) -> list[str]`

Return Python files under the configured source directory.

### `read_file(context: ToolContext, file_path: str) -> str`

Read a Python source file after validating its location.

### `write_doc_file(context: ToolContext, file_name: str, content: str) -> str`

Write Markdown documentation under the configured docs directory.

### `resolve_under_root(root: Path, path: str) -> Path`

Resolve an absolute or relative path from a trusted root.

### `relative_to_root(root: Path, path: Path) -> str`

Return a POSIX path for a file relative to the project root.

### `is_relative_to(path: Path, root: Path) -> bool`

Return whether a path is contained within a root directory.
