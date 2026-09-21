import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool as McpTool

from cleankoda.tools import (
    McpToolAdapter,
    ToolRegistry,
    connect_mcp_server,
    mcp_server_session,
)


class TestMcpIntegration(unittest.TestCase):

    def setUp(self) -> None:
        self.mock_session = AsyncMock()

    def test_mcp_tool_adapter_schema_mapping(self) -> None:
        mcp_tool = McpTool(
            name="query_db",
            description="Executes a database query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "The SQL query."}
                },
                "required": ["sql"],
            },
        )
        adapter = McpToolAdapter(mcp_tool=mcp_tool, session=self.mock_session)
        expected_schema = {
            "type": "function",
            "function": {
                "name": "query_db",
                "description": "Executes a database query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "The SQL query."}
                    },
                    "required": ["sql"],
                },
            },
        }
        self.assertEqual(adapter.schema, expected_schema)

    def test_register_mcp_session_and_schemas(self) -> None:
        async def _test() -> None:
            tool1 = McpTool(
                name="tool_one",
                description="First test tool.",
                inputSchema={"type": "object"},
            )
            tool2 = McpTool(
                name="tool_two",
                description="Second test tool.",
                inputSchema={"type": "object"},
            )
            self.mock_session.list_tools.return_value = ListToolsResult(
                tools=[tool1, tool2]
            )

            registry = ToolRegistry([])
            registered = await registry.register_mcp_session(self.mock_session)

            self.assertEqual(registered, ["tool_one", "tool_two"])
            schemas = registry.get_schemas()
            self.assertEqual(len(schemas), 2)
            self.assertEqual(schemas[0]["function"]["name"], "tool_one")
            self.assertEqual(schemas[1]["function"]["name"], "tool_two")

        asyncio.run(_test())

    def test_run_tool_forwarding_to_client_session(self) -> None:
        async def _test() -> None:
            mcp_tool = McpTool(
                name="fetch_issue",
                description="Fetch issue by ID.",
                inputSchema={"type": "object"},
            )
            self.mock_session.list_tools.return_value = ListToolsResult(
                tools=[mcp_tool]
            )
            self.mock_session.call_tool.return_value = CallToolResult(
                content=[TextContent(type="text", text="Issue details #101")],
                isError=False,
            )

            registry = ToolRegistry([])
            await registry.register_mcp_session(self.mock_session)

            mock_tool_call = MagicMock()
            mock_tool_call.function.name = "fetch_issue"
            mock_tool_call.function.arguments = '{"issue_id": "101"}'

            result = await registry.run_tool(mock_tool_call)

            self.assertEqual(result, "Issue details #101")
            self.mock_session.call_tool.assert_called_once_with(
                "fetch_issue", arguments={"issue_id": "101"}
            )

        asyncio.run(_test())

    def test_mcp_tool_error_handling(self) -> None:
        async def _test() -> None:
            mcp_tool = McpTool(
                name="failing_tool",
                description="Tool that reports failure.",
                inputSchema={"type": "object"},
            )
            self.mock_session.list_tools.return_value = ListToolsResult(
                tools=[mcp_tool]
            )
            self.mock_session.call_tool.return_value = CallToolResult(
                content=[TextContent(type="text", text="Connection refused")],
                isError=True,
            )

            registry = ToolRegistry([])
            await registry.register_mcp_session(self.mock_session)

            mock_tool_call = {
                "function": {
                    "name": "failing_tool",
                    "arguments": '{"param": "val"}',
                }
            }

            result = await registry.run_tool(mock_tool_call)

            self.assertIn("Error executing tool 'failing_tool'", result)
            self.assertIn("Connection refused", result)

        asyncio.run(_test())

    def test_mcp_tool_exception_handling(self) -> None:
        async def _test() -> None:
            mcp_tool = McpTool(
                name="raising_tool",
                description="Tool raising network exception.",
                inputSchema={"type": "object"},
            )
            self.mock_session.list_tools.return_value = ListToolsResult(
                tools=[mcp_tool]
            )
            self.mock_session.call_tool.side_effect = RuntimeError("Network timeout")

            registry = ToolRegistry([])
            await registry.register_mcp_session(self.mock_session)

            mock_tool_call = {
                "function": {
                    "name": "raising_tool",
                    "arguments": "{}",
                }
            }

            result = await registry.run_tool(mock_tool_call)

            self.assertIn("Error executing tool 'raising_tool'", result)
            self.assertIn("Network timeout", result)

        asyncio.run(_test())

    def test_connect_mcp_server_and_session_context_manager(self) -> None:
        async def _test() -> None:
            server_path = "src/cleankoda/tools/mcp/issue_mcp_server.py"
            async with mcp_server_session(sys.executable, [server_path]) as session:
                registry = ToolRegistry([])
                registered = await registry.register_mcp_session(session)
                self.assertIn("get_issues", registered)
                self.assertIn("get_issue_details", registered)

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
