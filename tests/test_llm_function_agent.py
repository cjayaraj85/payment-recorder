from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from function_agent.llm_agent import LLMFunctionCallingAgent, parse_tool_arguments


class LLMFunctionCallingAgentTests(unittest.TestCase):
    def test_exposes_descriptive_workspace_tool_names(self) -> None:
        agent = LLMFunctionCallingAgent()
        tool_names = [tool["function"]["name"] for tool in agent.tools()]

        self.assertEqual(
            tool_names,
            [
                "list_workspace_files",
                "read_workspace_text_file",
                "terminate",
            ],
        )
        self.assertNotIn("list_files", tool_names)
        self.assertNotIn("read_file", tool_names)

    def test_executes_model_selected_list_workspace_files_tool(self) -> None:
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
                                            "name": "list_workspace_files",
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

            self.assertEqual(response.tool_name, "list_workspace_files")
            self.assertEqual(response.tool_args, {})
            self.assertEqual(response.result, {"files": ["alpha.txt", "folder/"]})
            self.assertEqual(captured["model"], "openai/gpt-4o")
            self.assertEqual(captured["tools"][0]["type"], "function")
            self.assertEqual(
                captured["tools"][0]["function"]["name"],
                "list_workspace_files",
            )

    def test_executes_model_selected_read_workspace_text_file_tool(self) -> None:
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
                                            "name": "read_workspace_text_file",
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

            self.assertEqual(response.tool_name, "read_workspace_text_file")
            self.assertEqual(response.tool_args, {"file_name": "README.md"})
            self.assertEqual(
                response.result,
                {"file_name": "README.md", "content": "# Demo\n"},
            )

    def test_legacy_tool_names_still_execute_as_hidden_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "alpha.txt").write_text("alpha", encoding="utf-8")

            agent = LLMFunctionCallingAgent(root=root)

            self.assertEqual(agent.execute_tool("list_files", {}), {"files": ["alpha.txt"]})
            self.assertEqual(
                agent.execute_tool("read_file", {"file_name": "alpha.txt"}),
                {"file_name": "alpha.txt", "content": "alpha"},
            )

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
                                            "name": "list_workspace_files",
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
            self.assertEqual(response.steps[0].tool_name, "list_workspace_files")
            self.assertEqual(response.steps[0].result, {"files": ["alpha.txt"]})
            self.assertEqual(response.steps[1].tool_name, "terminate")
            self.assertEqual(response.steps[1].result, {"message": "Listed the files."})
            self.assertIn('"files": ["alpha.txt"]', calls[1]["messages"][-1]["content"])

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
                                            "name": "read_workspace_text_file",
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
        self.assertIn("Invalid arguments for read_workspace_text_file", response.steps[0].error)
        self.assertIn("Invalid arguments for read_workspace_text_file", calls[1]["messages"][-1]["content"])

    def test_read_workspace_text_file_returns_guided_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            response = LLMFunctionCallingAgent(root=Path(tmp)).read_workspace_text_file(
                "missing.txt"
            )

            self.assertIn("error", response)
            self.assertIn("next_action", response)
            self.assertIn("list_workspace_files", response["next_action"])


if __name__ == "__main__":
    unittest.main()
