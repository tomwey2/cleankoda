import json
from typing import Any

from cleankoda.tools.tool_base import Tool
from cleankoda.sandbox import Sandbox


class BashCommand(Tool):
    """Agent tool for running shell commands in a sandbox environment."""

    def __init__(self, sandbox: Sandbox, timeout: int = 30) -> None:
        self.sandbox = sandbox
        self.timeout = timeout

    @property
    def schema(self) -> list[dict[str, Any]]:
      """OpenAI / LiteLLM Tool Schema definition."""
      return [
          {
              "type": "function",
              "function": {
                  "name": "run_bash",
                  "description": "Run a shell command and return its output. The user approves it first.",
                  "parameters": {
                      "type": "object",
                      "properties": {
                          "command": {"type": "string", "description": "The shell command to run"},
                      },
                      "required": ["command"],
                  },
              },
          },
      ]

    async def execute(self, command: str) -> str:
        """Executes a command in the active environment and returns a JSON result."""
        result = await self.sandbox.current_env.run(command=command, timeout=self.timeout)
        return json.dumps(result, ensure_ascii=False)
