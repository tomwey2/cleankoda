import asyncio
from pathlib import Path
from typing import Any

from cleankoda.tools.tool_base import Tool

class Glob(Tool):

    def __init__(self, workspace: Path):
        self.workspace_root = workspace.resolve()

    @property
    def schema(self) -> dict[str, Any]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "glob",
                    "description": (
                        "Primary tool for discovering and locating files across the repository"
                        " using patterns (e.g., '**/*.java', 'src/**/test*'). Searches recursively in a single step."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": (
                                    "Glob pattern to match files (e.g. '**/*.py',"
                                    " '**/*Test*.java')."
                                ),
                            },
                            "path": {
                                "type": "string",
                                "description": (
                                    "Optional relative base directory to search in"
                                    " (defaults to workspace root)."
                                ),
                                "default": ".",
                            },
                            "hidden": {
                                "type": "boolean",
                                "description": (
                                    "Whether to include hidden files/directories"
                                    " (starting with '.'). Defaults to false."
                                ),
                                "default": False,
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return.",
                                "default": 100,
                            },
                        },
                        "required": ["pattern"],
                    },
                },
        }
    ]

    def _glob_sync(
        self,
        pattern: str,
        path: str = ".",
        hidden: bool = False,
        limit: int = 100,
    ) -> str:
        base_dir = (self.workspace_root / path).resolve()

        # Sandboxing: Verhindern, dass außerhalb des Workspaces gesucht wird
        if (
            not base_dir.is_relative_to(self.workspace_root)
            or not base_dir.is_dir()
        ):
            return f"Error: Path '{path}' is invalid or outside the workspace."

        results: list[str] = []

        try:
            # rglob/glob Matcher
            for item in base_dir.glob(pattern):
                # Hidden-Files filtern (z.B. .git, .idea), falls hidden=False
                if not hidden and any(part.startswith(".") for part in item.parts):
                    continue

                # Relativen Pfad zum Workspace für kompakte Ausgabe berechnen
                rel_path = item.relative_to(self.workspace_root)
                results.append(str(rel_path))

                if len(results) >= limit:
                    break

            if not results:
                return f"No files matched pattern '{pattern}'."

            # Nach Pfadtiefe und Name sortieren
            results.sort()
            header = f"Found {len(results)} matches"
            if len(results) >= limit:
                header += f" (truncated at limit {limit})"

            return f"{header}:\n" + "\n".join(results)

        except Exception as e:
            return f"Error executing glob pattern '{pattern}': {e}"


    async def execute(
        self,
        pattern: str,
        path: str = ".",
        hidden: bool = False,
        limit: int = 100,
    ) -> str:
        return await asyncio.to_thread(self._glob_sync, pattern, path, hidden, limit)
