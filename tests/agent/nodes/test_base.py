"""Unit tests for base.py node functions"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.nodes.base import _count_consecutive_exploration_calls


class TestCountConsecutiveExplorationCalls:
    """Tests for _count_consecutive_exploration_calls function"""

    def test_no_messages(self):
        """Test with empty message list"""
        result = _count_consecutive_exploration_calls([])
        assert result == 0

    def test_single_exploration_call(self):
        """Test with single exploration tool call"""
        msg = AIMessage(content="", tool_calls=[{"name": "list_files", "args": {}, "id": "1"}])
        result = _count_consecutive_exploration_calls([msg])
        assert result == 1

    def test_multiple_consecutive_exploration_calls(self):
        """Test with multiple consecutive exploration tool calls"""
        messages = [
            AIMessage(content="", tool_calls=[{"name": "list_files", "args": {}, "id": "1"}]),
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {}, "id": "2"}]),
            AIMessage(content="", tool_calls=[{"name": "list_files", "args": {}, "id": "3"}]),
        ]
        result = _count_consecutive_exploration_calls(messages)
        assert result == 3

    def test_exploration_calls_broken_by_non_exploration(self):
        """Test that non-exploration tool calls break the streak"""
        messages = [
            AIMessage(content="", tool_calls=[{"name": "list_files", "args": {}, "id": "1"}]),
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {}, "id": "2"}]),
            AIMessage(content="", tool_calls=[{"name": "write_to_file", "args": {}, "id": "3"}]),
            AIMessage(content="", tool_calls=[{"name": "list_files", "args": {}, "id": "4"}]),
        ]
        result = _count_consecutive_exploration_calls(messages)
        assert result == 1

    def test_exploration_calls_broken_by_tool_message(self):
        """Test that ToolMessage doesn't break the streak"""
        messages = [
            AIMessage(content="", tool_calls=[{"name": "list_files", "args": {}, "id": "1"}]),
            ToolMessage(content="result", tool_call_id="1"),
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {}, "id": "2"}]),
        ]
        result = _count_consecutive_exploration_calls(messages)
        assert result == 2

    def test_exploration_calls_broken_by_human_message(self):
        """Test that HumanMessage doesn't break the streak"""
        messages = [
            AIMessage(content="", tool_calls=[{"name": "list_files", "args": {}, "id": "1"}]),
            HumanMessage(content="user input"),
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {}, "id": "2"}]),
        ]
        result = _count_consecutive_exploration_calls(messages)
        assert result == 2

    def test_ai_message_without_tool_calls_breaks_streak(self):
        """Test that AIMessage without tool_calls doesn't break the streak"""
        messages = [
            AIMessage(content="", tool_calls=[{"name": "list_files", "args": {}, "id": "1"}]),
            AIMessage(content="thinking"),
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {}, "id": "2"}]),
        ]
        result = _count_consecutive_exploration_calls(messages)
        assert result == 2

    def test_mixed_exploration_and_non_exploration_in_single_message(self):
        """Test AIMessage with both exploration and non-exploration tools counts as exploration"""
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "list_files", "args": {}, "id": "1"},
                {"name": "write_to_file", "args": {}, "id": "2"},
            ],
        )
        result = _count_consecutive_exploration_calls([msg])
        assert result == 1

    def test_counts_from_end_of_list(self):
        """Test that counting starts from the end of the message list"""
        messages = [
            AIMessage(content="", tool_calls=[{"name": "write_to_file", "args": {}, "id": "1"}]),
            HumanMessage(content="user input"),
            AIMessage(content="", tool_calls=[{"name": "list_files", "args": {}, "id": "2"}]),
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {}, "id": "3"}]),
        ]
        result = _count_consecutive_exploration_calls(messages)
        assert result == 2

    def test_only_read_file_calls(self):
        """Test with only read_file exploration calls"""
        messages = [
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {}, "id": "1"}]),
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {}, "id": "2"}]),
        ]
        result = _count_consecutive_exploration_calls(messages)
        assert result == 2

    def test_empty_tool_calls_list_breaks_streak(self):
        """Test that AIMessage with empty tool_calls list doesn't break the streak"""
        messages = [
            AIMessage(content="", tool_calls=[{"name": "list_files", "args": {}, "id": "1"}]),
            AIMessage(content="", tool_calls=[]),
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {}, "id": "2"}]),
        ]
        result = _count_consecutive_exploration_calls(messages)
        assert result == 2
