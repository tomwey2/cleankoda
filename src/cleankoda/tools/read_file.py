import asyncio
from typing import Any
from pathlib import Path

from cleankoda.tools.tool_base import Tool

class ReadFile(Tool):

    def __init__(self, workspace: Path):
        self.workspace_root = workspace.resolve()

    @property
    def schema(self) -> list[dict[str, Any]]:
      """OpenAI / LiteLLM Tool Schema definition."""
      return [
          {
              "type": "function",
              "function": {
                  "name": "read_file",
                  "description": "Read a text file and return its contents.",
                  "parameters": {
                      "type": "object",
                      "properties": {
                          "path": {"type": "string", "description": "Path of the file to read"},
                      },
                      "required": ["path"],
                  },
              },
          },
      ]

    def _resolve_safe_path(self, relative_path: str | Path) -> Path:
        target = (self.workspace_root / relative_path).resolve()
        try:
            target.relative_to(self.workspace_root)
        except ValueError:
            raise PermissionError(f"Access Denied: '{relative_path}' points outside workspace root.")
        return target


    def _read_sync(self, path: str, max_chars: int = 50_000) -> str:
        safe_path = self._resolve_safe_path(path)
        if not safe_path.exists():
            return f"Error: File '{path}' does not exist."
        if safe_path.is_dir():
            return f"Error: '{path}' is a directory, not a file."

        content = safe_path.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_chars:
            return content[:max_chars] + f"\n\n[... Truncated after {max_chars} characters ...]"
        return content

    async def execute(self, path: str) -> str:
        return await asyncio.to_thread(self._read_sync, path)
