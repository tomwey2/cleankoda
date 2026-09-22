import json
import asyncio
from typing import Any
from pathlib import Path

from cleankoda.tools.tool_base import Tool

class ListDir(Tool):

    def __init__(self, workspace: Path):
        self.workspace_root = workspace.resolve()

    @property
    def schema(self) -> list[dict[str, Any]]:
      """OpenAI / LiteLLM Tool Schema definition."""
      return [
          {
              "type": "function",
              "function": {
                  "name": "list_dir",
                  "description": (
                        "Lists only immediate, top-level contents of a single directory (shallow / non-recursive)."
                        " Use ONLY for inspecting the root structure or specific single folders."
                        " Do NOT use this to search or hunt for files across subdirectories—use 'glob' instead."
                  ),
                  "parameters": {
                      "type": "object",
                      "properties": {
                          "path": {"type": "string", "description": "Directory to list, e.g. '.'"},
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

    def _list_sync(self, path: str = ".") -> str:
        safe_path = self._resolve_safe_path(path)
        if not safe_path.exists():
            return f"Error: Directory '{path}' does not exist."
        if not safe_path.is_dir():
            return f"Error: '{path}' is a file, not a directory."

        items = []
        for item in sorted(safe_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            prefix = "[DIR] " if item.is_dir() else "      "
            items.append(f"{prefix}{item.name}")
        return "\n".join(items) if items else "(Empty directory)"

    async def execute(self, path: str = ".") -> str:
        return await asyncio.to_thread(self._list_sync, path)
