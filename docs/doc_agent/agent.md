# `doc_agent.agent`

Source: `src/doc_agent/agent.py`

## Summary

Agent orchestration for source scanning and documentation writing.

## Classes

### `AgentRunResult`

Summary of one documentation agent run.

Methods: none.

### `DocumentationAgent`

Agent that uses structured file tools to generate Markdown docs.

Methods:

- `__init__(self, executor: ToolExecutor, src_dir: str = 'src')`
- `run(self) -> AgentRunResult`
- `_execute(self, action: Dict[str, Any], tool_calls: List[ToolCallResult]) -> ToolCallResult`

## Functions

No top-level functions found.
