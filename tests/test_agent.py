import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cleankoda.agent import Agent
from cleankoda.llm import LLMService
from cleankoda.memory import Memory
from cleankoda.sandbox import Sandbox
from cleankoda.state import SessionState, get_session_state
from cleankoda.tools import Bash, ListDir, ReadFile, ToolRegistry, WriteFile


class TestAgentLoop(unittest.TestCase):

    def test_agent_class_instantiation(self):
        mem = Memory(system_prompt="Test")
        sb = Sandbox(default_image_id=None, workspace=Path.cwd())
        tools = [
            ListDir(workspace=Path.cwd()),
            ReadFile(workspace=Path.cwd()),
            WriteFile(workspace=Path.cwd()),
            Bash(sandbox=sb),
        ]
        agent = Agent(
            memory=mem,
            tools=tools,
            sandbox=sb,
        )
        self.assertEqual(agent.memory, mem)
        self.assertEqual(agent.sandbox, sb)
        self.assertIsInstance(agent.llm_service, LLMService)
        self.assertIsInstance(agent.tool_registry, ToolRegistry)

    def test_run_agent_basic_completion(self):
        async def _test():
            mem = Memory(system_prompt="Test")
            mem.add_user("Hello agent")

            async def mock_stream_llm(messages, **kwargs):
                chunks_out = kwargs.get("chunks_out")
                if chunks_out is not None:
                    chunks_out.append({
                        "id": "1",
                        "object": "chat.completion.chunk",
                        "created": 12345,
                        "model": "gpt-4o",
                        "choices": [{
                            "index": 0,
                            "delta": {"role": "assistant", "content": "Hello user!"},
                            "finish_reason": "stop"
                        }]
                    })
                yield "Hello user!"

            with patch("cleankoda.agent.LLMService.stream_completion", side_effect=mock_stream_llm):
                tokens = []
                sb = Sandbox(default_image_id=None, workspace=Path.cwd())
                tools = [
                    ListDir(workspace=Path.cwd()),
                    ReadFile(workspace=Path.cwd()),
                    WriteFile(workspace=Path.cwd()),
                    Bash(sandbox=sb),
                ]
                agent = Agent(memory=mem, tools=tools, sandbox=sb)
                async for token in agent.run():
                    tokens.append(token)

            self.assertEqual("".join(tokens), "Hello user!")
            self.assertEqual(mem.messages[-1]["role"], "assistant")
            self.assertEqual(mem.messages[-1]["content"], "Hello user!")

        asyncio.run(_test())

    def test_run_agent_custom_tools_and_cancellation(self):
        async def _test():
            mem = Memory(system_prompt="Test")
            cancel_event = asyncio.Event()

            async def mock_stream_llm(messages, **kwargs):
                self.assertEqual(kwargs.get("tools"), [{"type": "function", "function": {"name": "custom_tool"}}])
                yield "Running tool..."

            cancel_event.set()

            with patch("cleankoda.agent.LLMService.stream_completion", side_effect=mock_stream_llm):
                tokens = []
                sb = MagicMock()
                mock_tool = MagicMock()
                mock_tool.schema = [{"type": "function", "function": {"name": "custom_tool"}}]
                agent = Agent(
                    memory=mem,
                    tools=[mock_tool],
                    sandbox=sb,
                )
                async for token in agent.run(cancel_event=cancel_event):
                    tokens.append(token)

            self.assertIn("Agent execution cancelled.", "".join(tokens))

        asyncio.run(_test())

    def test_run_agent_status_callback_invocation(self):
        async def _test():
            mem = Memory(system_prompt="Test")
            statuses = []

            def status_cb(st: SessionState):
                statuses.append(st.get_combined_status())

            tool_chunk = {
                "id": "1",
                "object": "chat.completion.chunk",
                "created": 12345,
                "model": "gpt-4o",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "tool_calls": [{
                            "index": 0,
                            "id": "call_123",
                            "type": "function",
                            "function": {"name": "list_files", "arguments": "{}"}
                        }]
                    },
                    "finish_reason": "tool_calls"
                }]
            }

            text_chunk = {
                "id": "2",
                "object": "chat.completion.chunk",
                "created": 12345,
                "model": "gpt-4o",
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": "Done."},
                    "finish_reason": "stop"
                }]
            }

            call_count = 0

            async def mock_stream_llm(messages, **kwargs):
                nonlocal call_count
                call_count += 1
                chunks_out = kwargs.get("chunks_out")
                if call_count == 1:
                    if chunks_out is not None:
                        chunks_out.append(tool_chunk)
                else:
                    if chunks_out is not None:
                        chunks_out.append(text_chunk)
                    yield "Done."

            mock_sandbox = MagicMock()
            mock_tool = MagicMock()
            mock_tool.schema = [{"type": "function", "function": {"name": "list_files"}}]
            mock_tool.execute = AsyncMock(return_value="file1.txt")

            get_session_state().subscribe(status_cb)
            with patch("cleankoda.agent.LLMService.stream_completion", side_effect=mock_stream_llm):
                tokens = []
                agent = Agent(
                    memory=mem,
                    tools=[mock_tool],
                    sandbox=mock_sandbox,
                )
                async for token in agent.run():
                    tokens.append(token)

                output = "".join(tokens)
                self.assertIn("list_files", output)
                self.assertIn("Done.", output)
                self.assertTrue(any("Execute tool: list_files" in s for s in statuses if s))

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
