from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from doc_agent.agent import DocumentationAgent
from doc_agent.executor import ToolExecutionError, ToolExecutor
from doc_agent.tools import ToolContext, build_tool_registry


class DocumentationAgentTests(unittest.TestCase):
    def test_tool_metadata_describes_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = ToolExecutor(
                build_tool_registry(ToolContext(project_root=Path(tmp)))
            )

            metadata = {tool["tool_name"]: tool for tool in executor.metadata()}

            self.assertEqual(
                set(metadata),
                {"list_python_files", "read_file", "write_doc_file"},
            )
            self.assertEqual(
                metadata["read_file"]["parameters"]["required"],
                ["file_path"],
            )
            self.assertEqual(
                metadata["write_doc_file"]["parameters"]["required"],
                ["file_name", "content"],
            )

    def test_executor_validates_action_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = ToolExecutor(
                build_tool_registry(ToolContext(project_root=Path(tmp)))
            )

            with self.assertRaises(ToolExecutionError):
                executor.execute({"tool_name": "read_file", "args": {}})

            with self.assertRaises(ToolExecutionError):
                executor.execute(
                    {
                        "tool_name": "read_file",
                        "args": {"file_path": "src/example.py", "extra": "nope"},
                    }
                )

            with self.assertRaises(ToolExecutionError):
                executor.execute({"tool_name": "missing_tool", "args": {}})

    def test_agent_generates_markdown_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            source_dir = project_root / "src"
            source_dir.mkdir()
            (source_dir / "example.py").write_text(
                '''"""Example module."""


class Greeter:
    """Greets people."""

    def hello(self, name: str) -> str:
        """Return a greeting."""
        return f"Hello {name}"


def add(left: int, right: int) -> int:
    """Add two numbers."""
    return left + right
''',
                encoding="utf-8",
            )

            context = ToolContext(project_root=project_root)
            executor = ToolExecutor(build_tool_registry(context))
            result = DocumentationAgent(executor).run()

            doc_path = project_root / "docs" / "example.md"
            content = doc_path.read_text(encoding="utf-8")

            self.assertEqual(result.files_documented, 1)
            self.assertIn("docs/example.md", result.docs_written)
            self.assertIn("# `example`", content)
            self.assertIn("### `Greeter`", content)
            self.assertIn("### `add(left: int, right: int) -> int`", content)


if __name__ == "__main__":
    unittest.main()

