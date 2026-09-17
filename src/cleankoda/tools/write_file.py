import json
import asyncio
from typing import Any
from pathlib import Path

from cleankoda.tools.tool_base import Tool

class WriteFile(Tool):

    def __init__(self, workspace: Path):
        self.workspace_root = workspace.resolve()

    @property
    def schema(self) -> list[dict[str, Any]]:
      """OpenAI / LiteLLM Tool Schema definition."""
      return [
          {
              "type": "function",
              "function": {
                  "name": "write_file",
                  "description": "Create or overwrite a text file with the given content.",
                  "parameters": {
                      "type": "object",
                      "properties": {
                          "path": {"type": "string", "description": "Path of the file to write"},
                          "content": {"type": "string", "description": "Full contents of the file"},
                      },
                      "required": ["path", "content"],
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

    def _write_sync(self, path: str, content: str) -> str:
        safe_path = self._resolve_safe_path(path)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to '{path}'."

    async def execute(self, path: str, content: str) -> str:
        return await asyncio.to_thread(self._write_sync, path, content)
