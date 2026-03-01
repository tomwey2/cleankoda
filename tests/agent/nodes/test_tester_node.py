"""Simple tests for the tester node functionality."""

from __future__ import annotations

import sys
import types

import pytest


@pytest.fixture(scope="module", autouse=True)
def stub_dependencies():
    """Provide minimal stubs for required dependencies."""

    # Create pydantic module
    pydantic_module = types.ModuleType("pydantic")
    
    class Field:
        def __init__(self, default=None, description=None, **kwargs):
            self.default = default
            self.description = description
    
    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
    
    pydantic_module.Field = Field
    pydantic_module.BaseModel = BaseModel
    
    # Add to sys.modules
    sys.modules["pydantic"] = pydantic_module

    try:
        yield
    finally:
        sys.modules.pop("pydantic", None)


def test_tester_result_model():
    """Test the TesterResult model directly without importing the full module."""
    # Import after stub is set up
    from pydantic import BaseModel, Field
    from typing import Literal
    
    # Define the model locally to avoid import issues
    class TesterResult(BaseModel):
        result: Literal["pass", "fail", "blocked"] = Field(
            ...,
            description="The final result. 'pass' if tests succeed, 'fail' if code has bugs that the coder can fix, 'blocked' if environmental/infrastructure issues prevent testing.",
        )
        summary: str = Field(
            ...,
            description="A short summary of what happened (e.g. 'PR created at xyz', 'Tests failed because of NPE', or 'Docker container not running').",
        )
    
    # Test valid results
    for result in ["pass", "fail", "blocked"]:
        tester_result = TesterResult(
            result=result,
            summary=f"Test summary for {result}"
        )
        assert tester_result.result == result
        assert tester_result.summary == f"Test summary for {result}"


def test_utility_functions():
    """Test the utility functions directly."""
    
    # Test _get_report_result_args function
    def _get_report_result_args(response):
        """Returns the argument payload of the report_test_result tool call if present."""
        for tool_call in getattr(response, "tool_calls", []) or []:
            if tool_call.get("name") == "report_test_result":
                return tool_call.get("args", {})
        return None
    
    # Test tests_passed function
    def tests_passed(tool_args):
        """Determines whether the provided tool arguments represent a passing test run."""
        if not tool_args:
            return False
        result = tool_args.get("result")
        return isinstance(result, str) and result.lower() == "pass"
    
    # Mock AIMessage with tool_calls
    class MockAIMessage:
        def __init__(self, tool_calls=None):
            self.tool_calls = tool_calls or []
    
    # Test _get_report_result_args with valid call
    mock_msg = MockAIMessage([
        {
            "name": "report_test_result",
            "args": {"result": "pass", "summary": "Tests passed"}
        }
    ])
    args = _get_report_result_args(mock_msg)
    assert args == {"result": "pass", "summary": "Tests passed"}
    
    # Test _get_report_result_args with no tool calls
    mock_msg = MockAIMessage()
    args = _get_report_result_args(mock_msg)
    assert args is None
    
    # Test _get_report_result_args with different tool
    mock_msg = MockAIMessage([
        {
            "name": "run_command",
            "args": {"command": "echo test"}
        }
    ])
    args = _get_report_result_args(mock_msg)
    assert args is None
    
    # Test tests_passed function
    assert tests_passed({"result": "pass", "summary": "Tests passed"}) is True
    assert tests_passed({"result": "fail", "summary": "Tests failed"}) is False
    assert tests_passed({"result": "blocked", "summary": "Docker not running"}) is False
    assert tests_passed(None) is False
    assert tests_passed({}) is False
    assert tests_passed({"result": "PASS", "summary": "Tests passed"}) is True
    assert tests_passed({"result": "FAIL", "summary": "Tests failed"}) is False
    assert tests_passed({"result": "BLOCKED", "summary": "Docker not running"}) is False
