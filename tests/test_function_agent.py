from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from function_agent import FunctionCallingAgent
from function_agent.agent import choose_action
from function_agent.tools import ToolExecutionError


class FunctionCallingAgentTests(unittest.TestCase):
    def test_chooses_list_directory_for_current_directory_request(self) -> None:
        action = choose_action("tell me the files in the current directory")

        self.assertEqual(
            action,
            {"tool_name": "list_directory", "args": {"path": "."}},
        )

    def test_lists_files_in_current_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "alpha.txt").write_text("alpha", encoding="utf-8")
            (root / "nested").mkdir()

            response = FunctionCallingAgent(root).run(
                "tell me the files in the current directory"
            )

            self.assertEqual(response.tool_result.tool_name, "list_directory")
            self.assertEqual(response.tool_result.result, ["alpha.txt", "nested/"])
            self.assertIn("Tool choice", response.format())

    def test_reads_text_file_when_path_is_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")

            response = FunctionCallingAgent(root).run("read README.md")

            self.assertEqual(response.tool_result.tool_name, "read_text_file")
            self.assertEqual(response.tool_result.result, "# Demo\n")

    def test_unsupported_request_does_not_call_tool(self) -> None:
        response = FunctionCallingAgent(Path.cwd()).run("send an email to the team")

        self.assertIsNone(response.action)
        self.assertIsNone(response.tool_result)
        self.assertIn("do not have a safe tool", response.message)

    def test_tool_rejects_paths_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = FunctionCallingAgent(root)

            with self.assertRaises(ToolExecutionError):
                agent.run("read ../outside.txt")


if __name__ == "__main__":
    unittest.main()

