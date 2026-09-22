"""Agent orchestration module for cleankoda.

Provides the `Agent` class and `AgentLifecycle` enum which orchestrate the ReAct
(Reasoning + Acting + Observation) loop, interfacing with LLM streaming services,
tool execution in the sandbox, memory retention, and UI status updates.
"""

import asyncio
from enum import Enum, auto
from typing import Any, AsyncGenerator

from litellm import stream_chunk_builder

from cleankoda.llm import LLMService
from cleankoda.memory import Memory
from cleankoda.prompts import SYSTEM_PROMPT
from cleankoda.sandbox import Sandbox
from cleankoda.state import get_active_issue
from cleankoda.statusline import statusline
from cleankoda.tools import Tool, ToolRegistry


class AgentLifecycle(Enum):
    """Lifecycle states of the AI agent."""

    IDLE = auto()
    """Agent is idle and waiting for user input."""

    THINKING = auto()
    """Agent is requesting LLM completion or streaming reasoning chunks."""

    EXECUTING = auto()
    """Agent is currently executing a tool call."""

    AWAITING_CONFIRMATION = auto()
    """Agent is awaiting user confirmation before proceeding with tool execution."""

    ERROR = auto()
    """Agent encountered an error state."""


class Agent:
    """Central agent orchestrator managing the ReAct execution loop."""

    def __init__(
        self,
        memory: Memory,
        tools: list[Tool],
        sandbox: Sandbox,
        base_system_prompt: str | None = None,
    ) -> None:
        """Initialize the Agent orchestrator.

        Args:
            memory: Memory instance maintaining conversation history.
            tools: List of available Tool instances.
            sandbox: Sandbox environment for command and tool execution.
            base_system_prompt: Optional base system prompt override; defaults to SYSTEM_PROMPT.
        """
        self.memory: Memory = memory
        self.sandbox = sandbox
        self.llm_service = LLMService()
        self.tool_registry = ToolRegistry(tools)
        self.state = AgentLifecycle.IDLE
        self.base_system_prompt: str = base_system_prompt or SYSTEM_PROMPT

    async def run(
        self,
        cancel_event: asyncio.Event | None = None,
        max_tool_iterations: int = 25,
    ) -> AsyncGenerator[str, None]:
        """Run the main agent ReAct loop.

        Iteratively requests completions from the LLM service, streams responses,
        executes requested tools via the tool registry, and updates conversation memory.

        Args:
            cancel_event: Optional asyncio Event to check for cancellation requests.
            max_tool_iterations: Maximum number of tool reasoning/action iterations allowed.

        Yields:
            Streamed text response chunks and formatted tool call display strings.
        """
        active = get_active_issue()
        if active:
            dynamic_system_prompt = f"{self.base_system_prompt}{active.to_system_prompt_snippet()}"
        else:
            dynamic_system_prompt = self.base_system_prompt
        self.memory.set_system_prompt(dynamic_system_prompt)

        iteration = 0

        try:
            # The ReAct Loop: Reasoning + Acting + Observation
            while iteration < max_tool_iterations:
                # 1. Reasoning (Thought): Request completion and stream LLM response
                self._set_state(AgentLifecycle.THINKING)

                if cancel_event is not None and cancel_event.is_set():
                    yield "[yellow]Agent execution cancelled.[/yellow]\n"
                    break

                iteration += 1
                chunks: list[Any] = []

                schemas = self.tool_registry.get_schemas()
                async for chunk in self.llm_service.stream_completion(
                    messages=self.memory.get_messages(),
                    tools=schemas,
                    cancel_event=cancel_event,
                    chunks_out=chunks,
                ):
                    yield chunk

                if cancel_event is not None and cancel_event.is_set():
                    break

                if not chunks:
                    break

                # Reconstruct response message to inspect tool calls
                stream_response_obj = stream_chunk_builder(chunks)
                response_msg = stream_response_obj.choices[0].message

                tool_calls = getattr(response_msg, "tool_calls", None)
                if not tool_calls:
                    # No tool calls requested (LLM provided final text response) - exit agent loop
                    content_text = getattr(response_msg, "content", None)
                    if content_text:
                        last_msg = self.memory.messages[-1] if self.memory.messages else None
                        last_role = last_msg.get("role") if isinstance(last_msg, dict) else getattr(last_msg, "role", None)
                        if last_role != "assistant":
                            self.memory.add_assistant(content_text)
                    break

                # Save assistant message with tool calls as a clean dictionary in memory
                if hasattr(response_msg, "model_dump"):
                    response_msg_dict = response_msg.model_dump(exclude_none=True)
                elif hasattr(response_msg, "dict"):
                    response_msg_dict = response_msg.dict(exclude_none=True)
                elif isinstance(response_msg, dict):
                    response_msg_dict = response_msg
                else:
                    response_msg_dict = {"role": "assistant"}

                if isinstance(response_msg_dict, dict):
                    response_msg_dict["role"] = "assistant"

                self.memory.add_message(response_msg_dict)

                # 2. Action: Execute proposed tool calls
                cancelled_in_tools = False
                for tool_call in tool_calls:
                    if cancel_event is not None and cancel_event.is_set():
                        yield "[yellow]Tool execution cancelled.[/yellow]\n"
                        cancelled_in_tools = True
                        break

                    func = getattr(tool_call, "function", None)
                    func_name = getattr(func, "name", "unknown") if func else "unknown"
                    func_args = getattr(func, "arguments", "") if func else ""
                    tool_call_id = getattr(tool_call, "id", "") or f"call_{func_name}"

                    display_str = self.llm_service.format_tool_call_display(func_name, func_args)
                    yield f"{display_str}\n"

                    try:
                        self._set_state(AgentLifecycle.EXECUTING, f"Execute tool: {func_name}...")
                        tool_result = await self.tool_registry.run_tool(tool_call)
                    finally:
                        self._set_state(AgentLifecycle.THINKING)

                    # 3. Observation (Feedback): Record tool execution results into memory
                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_result,
                    }
                    self.memory.add_message(tool_msg)

                if cancelled_in_tools:
                    break

        finally:
            # Agent loop finished cleanly or cancelled
            self._set_state(AgentLifecycle.IDLE)
            statusline.clear("agent")

    def is_busy(self) -> bool:
        """Check if the agent is currently busy.

        Returns:
            True if state is THINKING, EXECUTING, or AWAITING_CONFIRMATION; False otherwise.
        """
        return self.state in (
            AgentLifecycle.THINKING,
            AgentLifecycle.EXECUTING,
            AgentLifecycle.AWAITING_CONFIRMATION,
        )

    def _set_state(self, new_state: AgentLifecycle, detail: str | None = None) -> None:
        """Update internal lifecycle state and refresh status line.

        Args:
            new_state: Target AgentLifecycle state.
            detail: Optional descriptive text detailing the active state operation.
        """
        self.state = new_state
        msg = f"[{new_state.name}] {detail}" if detail else new_state.name
        statusline.set("agent", msg)
