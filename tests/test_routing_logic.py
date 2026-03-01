"""Test the core routing logic for the new 'blocked' result."""

# Mock AIMessage class - defined once for all tests
class MockAIMessage:
    def __init__(self, tool_calls=None):
        self.tool_calls = tool_calls or []


def test_routing_logic_blocked():
    """Test the routing logic for 'blocked' result."""
    
    # Routing function (copied from actual implementation)
    def route_after_tools_tester(state):
        """Routes flow after the tester's tools have run."""
        messages = state["messages"]

        # Ensure we have enough messages
        if len(messages) < 2:
            return "tester"

        # Look at the message BEFORE the tool output (the tester's AIMessage)
        last_ai_msg = messages[-2]

        if isinstance(last_ai_msg, MockAIMessage):
            # Only check valid parsed tool_calls that were actually executed
            tool_calls = last_ai_msg.tool_calls or []

            for tool_call in tool_calls:
                name = tool_call.get("name", "")
                if name == "report_test_result":
                    args = tool_call.get("args", {})
                    result = args.get("result") if isinstance(args, dict) else None

                    if result == "pass":
                        return "pass"  # Success -> End
                    if result == "blocked":
                        return "blocked"  # Environmental issue -> End with error
                    # Failed -> Back to the coder
                    return "failed"

        # If no 'report_test_result' was present, then return to the tester (loop)
        return "tester"
    
    # Test 'blocked' result
    state = {
        "messages": [
            MockAIMessage(tool_calls=[
                {
                    "name": "report_test_result",
                    "args": {"result": "blocked", "summary": "Docker container not running"}
                }
            ]),
            "some tool output message"
        ]
    }
    
    result = route_after_tools_tester(state)
    assert result == "blocked"


def test_routing_logic_pass():
    """Test the routing logic for 'pass' result."""
    
    # Routing function
    def route_after_tools_tester(state):
        """Routes flow after the tester's tools have run."""
        messages = state["messages"]

        if len(messages) < 2:
            return "tester"

        last_ai_msg = messages[-2]

        if isinstance(last_ai_msg, MockAIMessage):
            tool_calls = last_ai_msg.tool_calls or []

            for tool_call in tool_calls:
                name = tool_call.get("name", "")
                if name == "report_test_result":
                    args = tool_call.get("args", {})
                    result = args.get("result") if isinstance(args, dict) else None

                    if result == "pass":
                        return "pass"
                    if result == "blocked":
                        return "blocked"
                    return "failed"

        return "tester"
    
    # Test 'pass' result
    state = {
        "messages": [
            MockAIMessage(tool_calls=[
                {
                    "name": "report_test_result",
                    "args": {"result": "pass", "summary": "Tests passed"}
                }
            ]),
            "some tool output message"
        ]
    }
    
    result = route_after_tools_tester(state)
    assert result == "pass"


def test_routing_logic_fail():
    """Test the routing logic for 'fail' result."""
    
    # Routing function
    def route_after_tools_tester(state):
        """Routes flow after the tester's tools have run."""
        messages = state["messages"]

        if len(messages) < 2:
            return "tester"

        last_ai_msg = messages[-2]

        if isinstance(last_ai_msg, MockAIMessage):
            tool_calls = last_ai_msg.tool_calls or []

            for tool_call in tool_calls:
                name = tool_call.get("name", "")
                if name == "report_test_result":
                    args = tool_call.get("args", {})
                    result = args.get("result") if isinstance(args, dict) else None

                    if result == "pass":
                        return "pass"
                    if result == "blocked":
                        return "blocked"
                    return "failed"

        return "tester"
    
    # Test 'fail' result
    state = {
        "messages": [
            MockAIMessage(tool_calls=[
                {
                    "name": "report_test_result",
                    "args": {"result": "fail", "summary": "Tests failed"}
                }
            ]),
            "some tool output message"
        ]
    }
    
    result = route_after_tools_tester(state)
    assert result == "failed"


def test_routing_logic_no_report():
    """Test that without report_test_result, it loops back to tester."""
    
    # Routing function
    def route_after_tools_tester(state):
        """Routes flow after the tester's tools have run."""
        messages = state["messages"]

        if len(messages) < 2:
            return "tester"

        last_ai_msg = messages[-2]

        if isinstance(last_ai_msg, MockAIMessage):
            tool_calls = last_ai_msg.tool_calls or []

            for tool_call in tool_calls:
                name = tool_call.get("name", "")
                if name == "report_test_result":
                    args = tool_call.get("args", {})
                    result = args.get("result") if isinstance(args, dict) else None

                    if result == "pass":
                        return "pass"
                    if result == "blocked":
                        return "blocked"
                    return "failed"

        return "tester"
    
    # Test with different tool
    state = {
        "messages": [
            MockAIMessage(tool_calls=[
                {
                    "name": "run_command",
                    "args": {"command": "echo test"}
                }
            ]),
            "some tool output message"
        ]
    }
    
    result = route_after_tools_tester(state)
    assert result == "tester"
