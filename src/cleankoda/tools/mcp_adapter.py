from typing import Any

from mcp import ClientSession
from mcp.types import CallToolResult, Tool as McpTool

from cleankoda.tools.tool_base import Tool


class McpToolAdapter(Tool):
    """Adapter wrapping an MCP server tool into a local cleankoda Tool."""

    def __init__(self, mcp_tool: McpTool, session: ClientSession) -> None:
        self._mcp_tool = mcp_tool
        self._session = session
        self.name = mcp_tool.name

    @property
    def schema(self) -> dict[str, Any]:
        """Returns the LiteLLM / OpenAI tool schema definition."""
        input_schema = getattr(
            self._mcp_tool,
            "input_schema",
            getattr(self._mcp_tool, "inputSchema", {}),
        )
        return {
            "type": "function",
            "function": {
                "name": self._mcp_tool.name,
                "description": self._mcp_tool.description or "",
                "parameters": input_schema,
            },
        }

    async def execute(self, **kwargs: Any) -> str:
        """Executes the tool call via MCP ClientSession."""
        try:
            result: CallToolResult = await self._session.call_tool(
                self.name, arguments=kwargs
            )
            text_blocks: list[str] = []
            if result.content:
                for content in result.content:
                    if getattr(content, "type", None) == "text" or hasattr(content, "text"):
                        text_blocks.append(content.text)

            output = "\n".join(text_blocks)
            is_error = getattr(result, "is_error", getattr(result, "isError", False))
            if is_error:
                return f"Error executing tool '{self.name}': {output or 'Unknown error'}"
            return output
        except Exception as error:
            return f"Error executing tool '{self.name}': {error}"
