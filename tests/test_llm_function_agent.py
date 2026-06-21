from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from function_agent.llm_agent import LLMFunctionCallingAgent, parse_tool_arguments


class LLMFunctionCallingAgentTests(unittest.TestCase):
    def test_executes_model_selected_list_files_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "alpha.txt").write_text("alpha", encoding="utf-8")
            (root / "folder").mkdir()
            captured = {}

            def fake_completion(**kwargs):
                captured.update(kwargs)
                return {
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {
                                        "function": {
                                            "name": "list_files",
                                            "arguments": "{}",
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }

            response = LLMFunctionCallingAgent(
                root=root,
                completion_fn=fake_completion,
            ).run("tell me the files in the current directory")

            self.assertEqual(response.tool_name, "list_files")
            self.assertEqual(response.tool_args, {})
            self.assertEqual(response.result, ["alpha.txt", "folder/"])
            self.assertEqual(captured["model"], "openai/gpt-4o")
            self.assertEqual(captured["tools"][0]["type"], "function")
            self.assertEqual(captured["tools"][0]["function"]["name"], "list_files")

    def test_executes_model_selected_read_file_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")

            def fake_completion(**kwargs):
                return {
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {
                                        "function": {
                                            "name": "read_file",
                                            "arguments": '{"file_name": "README.md"}',
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }

            response = LLMFunctionCallingAgent(
                root=root,
                completion_fn=fake_completion,
            ).run("read README.md")

            self.assertEqual(response.tool_name, "read_file")
            self.assertEqual(response.tool_args, {"file_name": "README.md"})
            self.assertEqual(response.result, "# Demo\n")

    def test_returns_model_text_when_no_tool_is_called(self) -> None:
        def fake_completion(**kwargs):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "I can answer without calling a tool.",
                            "tool_calls": None,
                        }
                    }
                ]
            }

        response = LLMFunctionCallingAgent(completion_fn=fake_completion).run("hello")

        self.assertFalse(response.called_tool)
        self.assertEqual(response.result, "I can answer without calling a tool.")

    def test_parse_tool_arguments_accepts_dict_or_json_string(self) -> None:
        self.assertEqual(parse_tool_arguments({"file_name": "README.md"}), {"file_name": "README.md"})
        self.assertEqual(parse_tool_arguments('{"file_name": "README.md"}'), {"file_name": "README.md"})
        self.assertEqual(parse_tool_arguments(""), {})


if __name__ == "__main__":
    unittest.main()

