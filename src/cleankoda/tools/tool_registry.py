import asyncio
import inspect
import json
from typing import Any, Callable

from cleankoda.sandbox import Sandbox
from cleankoda.tools import Tool


class ToolRegistry:
    """Manages agent tools (filesystem & bash) and tool execution."""

    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._schemas: list[dict[str, Any]] = []
        if tools:
            for tool in tools:
                self.register(tool)

    def register(self, tool: Tool) -> None:
        """Registers a Tool instance into the registry."""
        raw_schema = tool.schema
        schemas = raw_schema if isinstance(raw_schema, list) else [raw_schema]
        for schema in schemas:
            func_dict = schema.get("function", {}) if schema.get("type") == "function" else schema
            name = func_dict.get("name")
            if not name:
                raise ValueError("Tool schema must include a function name.")
            self._tools[name] = tool.execute
            self._schemas.append(schema)

    def get_schemas(self) -> list[dict[str, Any]]:
        """Returns schemas of all registered tools."""
        return list(self._schemas)

    async def run_tool(self, tool_call: Any) -> str:
        """Executes a tool call using the tools registered in this registry."""
        func = getattr(tool_call, "function", None)
        if func:
            name = getattr(func, "name", None) or (func.get("name") if isinstance(func, dict) else None)
            args_str = getattr(func, "arguments", "{}") or (func.get("arguments") if isinstance(func, dict) else "{}")
        elif isinstance(tool_call, dict):
            fn_dict = tool_call.get("function", {})
            name = fn_dict.get("name")
            args_str = fn_dict.get("arguments", "{}")
        else:
            name = None
            args_str = "{}"

        if isinstance(args_str, str):
            try:
                args = json.loads(args_str) if args_str else {}
            except json.JSONDecodeError:
                args = {}
        else:
            args = args_str or {}

        if not name or name not in self._tools:
            return f"Error: Tool '{name}' not found."

        try:
            tool_func = self._tools[name]
            if asyncio.iscoroutinefunction(tool_func) or inspect.iscoroutinefunction(tool_func):
                return await tool_func(**args)
            res = tool_func(**args)
            if asyncio.iscoroutine(res):
                return await res
            return str(res)
        except Exception as error:
            return f"Error: {error}"
