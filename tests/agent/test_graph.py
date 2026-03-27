"""Tests for agent graph routing logic."""

from langchain_core.messages import AIMessage, ToolMessage

from app.agent.graph import route_after_tools_tester
from app.agent.state import AgentState


class TestRouteAfterToolsTester:
    """Test the tester routing logic for different test result states."""

    def test_route_pass_result(self):
        """Test that 'pass' result routes to pass (explainer)."""
        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "report_test_result",
                            "args": {"result": "pass", "summary": "All tests passed"},
                            "id": "1",
                        }
                    ],
                ),
                ToolMessage(content="Test result reported", tool_call_id="1"),
            ],
            "agent_task": None,
            "provider_task": None,
            "agent_summary": [],
        }
        result = route_after_tools_tester(state)
        assert result == "pass"

    def test_route_fail_result(self):
        """Test that 'fail' result routes to failed (coder)."""
        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "report_test_result",
                            "args": {"result": "fail", "summary": "Tests failed"},
                            "id": "1",
                        }
                    ],
                ),
                ToolMessage(content="Test result reported", tool_call_id="1"),
            ],
            "agent_task": None,
            "provider_task": None,
            "agent_summary": [],
        }
        result = route_after_tools_tester(state)
        assert result == "failed"

    def test_route_blocked_result(self):
        """Test that 'blocked' result routes to error (task_update)."""
        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "report_test_result",
                            "args": {
                                "result": "blocked",
                                "summary": "Docker container not running",
                            },
                            "id": "1",
                        }
                    ],
                ),
                ToolMessage(content="Test result reported", tool_call_id="1"),
            ],
            "agent_task": None,
            "provider_task": None,
            "agent_summary": [],
        }
        result = route_after_tools_tester(state)
        assert result == "error"

    def test_route_error_result(self):
        """Test that 'error' result routes to error (task_update)."""
        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "report_test_result",
                            "args": {
                                "result": "error",
                                "summary": "Maven not found",
                            },
                            "id": "1",
                        }
                    ],
                ),
                ToolMessage(content="Test result reported", tool_call_id="1"),
            ],
            "agent_task": None,
            "provider_task": None,
            "agent_summary": [],
        }
        result = route_after_tools_tester(state)
        assert result == "error"

    def test_route_no_report_test_result(self):
        """Test that non-report_test_result tool calls loop back to tester."""
        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "run_command",
                            "args": {"command": "mvn test"},
                            "id": "1",
                        }
                    ],
                ),
                ToolMessage(content="Command executed", tool_call_id="1"),
            ],
            "agent_task": None,
            "provider_task": None,
            "agent_summary": [],
        }
        result = route_after_tools_tester(state)
        assert result == "tester"

    def test_route_insufficient_messages(self):
        """Test that insufficient messages loop back to tester."""
        state: AgentState = {
            "messages": [
                AIMessage(content="Starting tests"),
            ],
            "agent_task": None,
            "provider_task": None,
            "agent_summary": [],
        }
        result = route_after_tools_tester(state)
        assert result == "tester"

    def test_route_unknown_result_treats_as_failure(self):
        """Test that unknown result values are treated as failures."""
        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "report_test_result",
                            "args": {
                                "result": "unknown_status",
                                "summary": "Something happened",
                            },
                            "id": "1",
                        }
                    ],
                ),
                ToolMessage(content="Test result reported", tool_call_id="1"),
            ],
            "agent_task": None,
            "provider_task": None,
            "agent_summary": [],
        }
        result = route_after_tools_tester(state)
        assert result == "failed"
