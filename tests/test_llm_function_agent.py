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

    def test_loop_runs_tools_until_terminate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "alpha.txt").write_text("alpha", encoding="utf-8")
            calls = []
            responses = [
                {
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
                },
                {
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {
                                        "function": {
                                            "name": "terminate",
                                            "arguments": '{"message": "Listed the files."}',
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                },
            ]

            def fake_completion(**kwargs):
                calls.append(kwargs)
                return responses[len(calls) - 1]

            response = LLMFunctionCallingAgent(
                root=root,
                completion_fn=fake_completion,
            ).run_loop("tell me the files in the current directory")

            self.assertTrue(response.terminated)
            self.assertEqual(response.final_message, "Listed the files.")
            self.assertEqual(response.stopped_reason, "terminated")
            self.assertEqual(len(response.steps), 2)
            self.assertEqual(response.steps[0].tool_name, "list_files")
            self.assertEqual(response.steps[0].result, {"result": ["alpha.txt"]})
            self.assertEqual(response.steps[1].tool_name, "terminate")
            self.assertIn('"result": ["alpha.txt"]', calls[1]["messages"][-1]["content"])

    def test_loop_returns_text_when_model_does_not_call_tool(self) -> None:
        def fake_completion(**kwargs):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "No tool is needed.",
                            "tool_calls": None,
                        }
                    }
                ]
            }

        response = LLMFunctionCallingAgent(completion_fn=fake_completion).run_loop("hello")

        self.assertFalse(response.terminated)
        self.assertEqual(response.final_message, "No tool is needed.")
        self.assertEqual(response.stopped_reason, "model_response")

    def test_loop_feeds_invalid_tool_arguments_back_to_model(self) -> None:
        calls = []
        responses = [
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "read_file",
                                        "arguments": "{bad json",
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "terminate",
                                        "arguments": '{"message": "Could not read the file."}',
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        ]

        def fake_completion(**kwargs):
            calls.append(kwargs)
            return responses[len(calls) - 1]

        response = LLMFunctionCallingAgent(completion_fn=fake_completion).run_loop("read bad")

        self.assertTrue(response.terminated)
        self.assertIn("Invalid arguments for read_file", response.steps[0].error)
        self.assertIn("Invalid arguments for read_file", calls[1]["messages"][-1]["content"])


if __name__ == "__main__":
    unittest.main()
