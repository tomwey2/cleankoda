from cleankoda.memory import MemoryInFile
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import litellm
from litellm.exceptions import (
    APIConnectionError,
    AuthenticationError,
    RateLimitError,
)

from cleankoda.agent import Agent
from cleankoda.config import AppConfig, config
from cleankoda.llm import LLMService


class TestLLMService(unittest.TestCase):

    def test_stream_llm_completion_success(self):
        async def _test():
            messages = [{"role": "user", "content": "Hello"}]

            mock_chunk1 = {"choices": [{"delta": {"content": "Hello"}}]}
            mock_chunk2 = {"choices": [{"delta": {"content": " world!"}}]}

            async def mock_acompletion(*args, **kwargs):
                self.assertEqual(kwargs.get("model"), "openai/gpt-4o")
                self.assertEqual(kwargs.get("api_key"), "test-key")
                self.assertTrue(kwargs.get("stream"))
                for chunk in [mock_chunk1, mock_chunk2]:
                    yield chunk

            with patch("litellm.acompletion", side_effect=mock_acompletion), patch.object(
                config, "provider", "openai"
            ), patch.object(config, "model", "gpt-4o"), patch.object(
                AppConfig, "get_active_api_key", return_value="test-key"
            ):
                chunks = []
                async for token in LLMService().stream_completion(messages, tools=[]):
                    chunks.append(token)

                self.assertEqual("".join(chunks), "Hello world!")

        asyncio.run(_test())

    def test_stream_llm_completion_ollama_no_api_key(self):
        async def _test():
            messages = [{"role": "user", "content": "Hello"}]

            async def mock_acompletion(*args, **kwargs):
                self.assertEqual(kwargs.get("api_key"), "dummy")
                self.assertEqual(kwargs.get("api_base"), "http://localhost:11434/v1")
                self.assertEqual(kwargs.get("model"), "ollama/llama3.3")
                mock_chunk = {"choices": [{"delta": {"content": "Ollama response"}}]}
                yield mock_chunk

            with patch("litellm.acompletion", side_effect=mock_acompletion), patch.object(
                config, "provider", "ollama"
            ), patch.object(config, "model", "llama3.3"):
                chunks = []
                async for token in LLMService().stream_completion(messages, tools=[]):
                    chunks.append(token)

                self.assertEqual("".join(chunks), "Ollama response")

        asyncio.run(_test())

    def test_stream_llm_completion_auth_error(self):
        async def _test():
            messages = [{"role": "user", "content": "Hello"}]

            auth_err = AuthenticationError(
                message="Invalid API Key",
                response=MagicMock(status_code=401),
                llm_provider="anthropic",
                model="claude-3-5-sonnet-latest",
            )

            with patch("litellm.acompletion", side_effect=auth_err), patch.object(
                config, "provider", "anthropic"
            ), patch.object(config, "model", "claude-3-5-sonnet-latest"):
                chunks = []
                async for token in LLMService().stream_completion(messages, tools=[]):
                    chunks.append(token)

                result = "".join(chunks)
                self.assertIn("Authentication Error", result)

        asyncio.run(_test())

    def test_run_agent_tool_execution(self):
        async def _test():
            import tempfile
            from pathlib import Path
            from cleankoda.memory import Memory

            with tempfile.TemporaryDirectory() as tmpdir:
                file_path = Path(tmpdir) / "memory.json"
                mem = MemoryInFile(system_prompt="Test", file=file_path)
                mem.add_user("List files")

            chunk_tool_1 = {
                "id": "chatcmpl-1",
                "object": "chat.completion.chunk",
                "created": 1234,
                "model": "gpt-4o",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "tool_calls": [{
                            "index": 0,
                            "id": "call_test123",
                            "type": "function",
                            "function": {"name": "list_files", "arguments": '{"path": "."}'}
                        }]
                    },
                    "finish_reason": "tool_calls"
                }]
            }

            chunk_text_2 = {
                "id": "chatcmpl-2",
                "object": "chat.completion.chunk",
                "created": 1235,
                "model": "gpt-4o",
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": "Done listing files."},
                    "finish_reason": "stop"
                }]
            }

            call_count = 0

            async def mock_acompletion(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                self.assertIn("tools", kwargs)
                if call_count == 1:
                    yield chunk_tool_1
                else:
                    yield chunk_text_2

            from cleankoda.tools import TOOL_SCHEMAS

            mock_sandbox = MagicMock()
            mock_tools = MagicMock()
            mock_tools.get_schemas.return_value = TOOL_SCHEMAS
            mock_tools.run_tool = AsyncMock(return_value="file1.txt\nfile2.txt")

            with patch("litellm.acompletion", side_effect=mock_acompletion):
                chunks = []
                agent = Agent(memory=mem, llm_service=LLMService(), tools=mock_tools)
                async for token in agent.run():
                    chunks.append(token)

                output = "".join(chunks)
                self.assertIn("list_files(.)", output)
                self.assertNotIn("Tool Output", output)
                self.assertIn("Done listing files.", output)
                mock_tools.run_tool.assert_called_once()
                self.assertEqual(call_count, 2)

        asyncio.run(_test())

    def test_llm_service_class_instance_methods(self):
        from cleankoda.llm import LLMService

        service = LLMService()
        self.assertEqual(service.format_tool_call_display("read_file", '{"path": "test.py"}'), "read_file(test.py)")
        err = APIConnectionError(message="OpenAIException - Loading model", llm_provider="custom", model="qwen")
        self.assertTrue(service.is_cold_start_error(err))


if __name__ == "__main__":
    unittest.main()
