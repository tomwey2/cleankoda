"""Unit tests for invoke_tool_node base helper."""

import asyncio

import anyio
from langchain_core.messages import AIMessage

from app.agent.nodes.base import invoke_tool_node


class _FakeLLM:
    """Fake LLM that tracks tool choices and simulates a timeout."""

    def __init__(self):
        self.tool_choices: list[str] = []
        self.call_count = 0

    def bind_tools(self, _tools, tool_choice="auto"):
        self.tool_choices.append(tool_choice)
        return self

    async def ainvoke(self, _messages):
        self.call_count += 1
        if self.call_count == 1:
            raise asyncio.TimeoutError
        return AIMessage(
            content="ok",
            tool_calls=[
                {
                    "name": "finish_task",
                    "args": {"summary": "done"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        )


async def _run_invoke(**kwargs):
    """Helper to execute invoke_tool_node inside anyio."""

    return await invoke_tool_node(**kwargs)


@anyio.run
async def test_invoke_tool_node_retries_after_timeout(monkeypatch):
    """invoke_tool_node should retry with tool_choice='any' after timeout."""

    fake_llm = _FakeLLM()

    monkeypatch.setattr("app.agent.nodes.base.filter_messages_for_llm", lambda *_: [])
    monkeypatch.setattr("app.agent.nodes.base.sanitize_response", lambda resp: resp)
    monkeypatch.setattr("app.agent.nodes.base.log_agent_response", lambda *args, **kwargs: None)

    state = {"messages": []}
    result = await _run_invoke(
        node_name="tester",
        state=state,
        llm=fake_llm,
        tools=[],
        system_prompt="system",
        human_prompt="human",
        max_messages=10,
        fallback_tool_name="finish_task",
        fallback_tool_args={"summary": "failed"},
        llm_response_hook=None,
    )

    assert result["current_node"] == "tester"
    assert result["messages"][0].tool_calls
    assert fake_llm.tool_choices == ["auto", "any"]
