import asyncio
import unittest
from unittest.mock import MagicMock, patch

from litellm.exceptions import (
    APIConnectionError,
    APIError,
    ServiceUnavailableError,
)

from cleankoda.llm.service import LLMService
from cleankoda.state import SessionState, get_session_state


class TestColdStartBackoff(unittest.TestCase):

    def test_is_cold_start_error_detection(self):
        err_503 = ServiceUnavailableError(
            message="503 Service Unavailable",
            response=MagicMock(status_code=503),
            llm_provider="custom",
            model="qwen",
        )
        service = LLMService()
        self.assertTrue(service.is_cold_start_error(err_503))

        err_loading = APIConnectionError(
            message="OpenAIException - Loading model",
            llm_provider="custom",
            model="qwen",
        )
        self.assertTrue(service.is_cold_start_error(err_loading))

        err_other = APIError(
            message="Invalid arguments",
            llm_provider="custom",
            model="qwen",
            status_code=400,
        )
        self.assertFalse(service.is_cold_start_error(err_other))

    def test_exponential_backoff_retry_success(self):
        async def _test():
            messages = [{"role": "user", "content": "Hello"}]

            call_count = 0
            delays_recorded = []

            async def mock_acompletion(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise ServiceUnavailableError(
                        message="503 Service Unavailable: Loading model",
                        response=MagicMock(status_code=503),
                        llm_provider="custom",
                        model="qwen",
                    )
                mock_chunk = {
                    "id": "chatcmpl-test",
                    "object": "chat.completion.chunk",
                    "created": 12345,
                    "model": "qwen",
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant", "content": "Model ready content"},
                        "finish_reason": "stop"
                    }]
                }
                yield mock_chunk

            async def mock_wait_for(fut, timeout):
                delays_recorded.append(timeout)
                raise asyncio.TimeoutError()

            cancel_event = asyncio.Event()
            with patch("litellm.acompletion", side_effect=mock_acompletion), patch(
                "asyncio.wait_for", side_effect=mock_wait_for
            ):
                chunks = []
                async for token in LLMService().stream_completion(
                    messages, tools=[], cancel_event=cancel_event, initial_delay=10.0, max_attempts=10
                ):
                    chunks.append(token)

                output = "".join(chunks)
                self.assertEqual(call_count, 3)
                self.assertEqual(delays_recorded, [10.0, 20.0])
                self.assertIn("attempt 1/10", output)
                self.assertIn("attempt 2/10", output)
                self.assertIn("✔ Model ready.", output)
                self.assertIn("Model ready content", output)

        asyncio.run(_test())

    def test_escape_cancellation(self):
        async def _test():
            messages = [{"role": "user", "content": "Hello"}]
            cancel_event = asyncio.Event()

            async def mock_acompletion(*args, **kwargs):
                raise ServiceUnavailableError(
                    message="Loading model",
                    response=MagicMock(status_code=503),
                    llm_provider="custom",
                    model="qwen",
                )

            async def mock_wait_for(fut, timeout):
                cancel_event.set()
                await fut
                return True

            with patch("litellm.acompletion", side_effect=mock_acompletion), patch(
                "asyncio.wait_for", side_effect=mock_wait_for
            ):
                chunks = []
                async for token in LLMService().stream_completion(
                    messages, tools=[], cancel_event=cancel_event, initial_delay=10.0, max_attempts=10
                ):
                    chunks.append(token)

                output = "".join(chunks)
                self.assertIn("attempt 1/10", output)
                self.assertIn("LLM startup aborted.", output)

        asyncio.run(_test())

    def test_max_attempts_exceeded(self):
        async def _test():
            messages = [{"role": "user", "content": "Hello"}]

            call_count = 0

            async def mock_acompletion(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                raise ServiceUnavailableError(
                    message="503 Service Unavailable: Loading model",
                    response=MagicMock(spec=["status_code"], status_code=503),
                    llm_provider="custom",
                    model="qwen",
                )

            async def mock_sleep(delay):
                pass

            with patch("litellm.acompletion", side_effect=mock_acompletion), patch(
                "asyncio.sleep", side_effect=mock_sleep
            ):
                chunks = []
                async for token in LLMService().stream_completion(
                    messages, tools=[], initial_delay=1.0, max_attempts=3
                ):
                    chunks.append(token)

                output = "".join(chunks)
                self.assertEqual(call_count, 4)
                self.assertIn("LLM could not be started after 3 attempts.", output)

        asyncio.run(_test())

    def test_status_callback_cold_start(self):
        async def _test():
            messages = [{"role": "user", "content": "Hello"}]
            statuses_received = []

            def status_cb(st: SessionState):
                statuses_received.append(st.get_combined_status())

            call_count = 0

            async def mock_acompletion(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ServiceUnavailableError(
                        message="503 Service Unavailable: Loading model",
                        response=MagicMock(status_code=503),
                        llm_provider="custom",
                        model="qwen",
                    )
                mock_chunk = {
                    "id": "chatcmpl-test",
                    "object": "chat.completion.chunk",
                    "created": 12345,
                    "model": "qwen",
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant", "content": "Ready content"},
                        "finish_reason": "stop"
                    }]
                }
                yield mock_chunk

            async def mock_wait_for(fut, timeout):
                raise asyncio.TimeoutError()

            get_session_state().subscribe(status_cb)

            cancel_event = asyncio.Event()
            with patch("litellm.acompletion", side_effect=mock_acompletion), patch(
                "asyncio.wait_for", side_effect=mock_wait_for
            ):
                chunks = []
                async for token in LLMService().stream_completion(
                    messages,
                    tools=[],
                    cancel_event=cancel_event,
                    initial_delay=10.0,
                    max_attempts=10,
                ):
                    chunks.append(token)

                output = "".join(chunks)
                self.assertIn("Ready content", output)
                self.assertTrue(any("attempt 1/10" in s for s in statuses_received if s))

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
