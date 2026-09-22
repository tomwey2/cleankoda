"""Bash execution tool module for cleankoda.

Provides the `Bash` tool and `prune_output` helper for running shell commands in a sandbox
environment with configurable timeouts and language-agnostic output pruning.
"""

import json
import re
from typing import Any

from cleankoda.sandbox import Sandbox
from cleankoda.tools.tool_base import Tool

RE_ERROR = re.compile(
    r"(?i)error|fail|exception|fatal|traceback|compilation error"
)

# Erkennt absolute Zugriffe auf sensible Systempfade
BLOCKED_SYSTEM_PATHS = re.compile(
    r"(?:^|[\s;&|`$\(])(/etc|/proc|/sys|/root|/var|/dev)(?:/|[\s;&|`\)]|$)",
    re.IGNORECASE,
)

# Erkennt gefährliche Traversal-Muster über die Sandbox-Grenzen hinweg
DANGEROUS_TRAVERSAL = re.compile(
    r"\.\./\.\./",  # Zwei oder mehr Ebenen nach oben
)

def _prune_stream(text: str | None, exit_code: int) -> str:
    """Prune a single output stream based on exit code and line/character limits."""
    if not text:
        return ""

    lines = text.splitlines()

    if exit_code == 0:
        if len(lines) > 60:
            first_15 = lines[:15]
            last_35 = lines[-35:]
            omitted = len(lines) - 50
            res_lines = first_15 + [f"[... {omitted} lines omitted ...]"] + last_35
        else:
            res_lines = lines
    else:
        if len(lines) > 40:
            last_40 = lines[-40:]
            prefix_lines = lines[:-40]
            error_lines = [line for line in prefix_lines if RE_ERROR.search(line)][:30]
            omitted = len(lines) - 40 - len(error_lines)
            if omitted > 0:
                res_lines = error_lines + [f"[... {omitted} lines omitted ...]"] + last_40
            else:
                res_lines = error_lines + last_40
        else:
            res_lines = lines

    pruned = "\n".join(res_lines)
    if len(pruned) > 8000:
        pruned = pruned[:8000]

    return pruned


def prune_output(stdout: str, stderr: str, exit_code: int) -> tuple[str, str]:
    """Prunes stdout and stderr output streams based on execution exit code and line limits."""
    return _prune_stream(stdout, exit_code), _prune_stream(stderr, exit_code)


class Bash(Tool):
    """Agent tool for running shell commands in a sandbox environment."""

    def __init__(self, sandbox: Sandbox, timeout: int = 120) -> None:
        """Initialize the Bash tool.

        Args:
            sandbox: Sandbox environment instance.
            timeout: Command execution timeout in seconds (default: 120).
        """
        self.sandbox = sandbox
        self.timeout = timeout

    @property
    def schema(self) -> list[dict[str, Any]]:
        """OpenAI / LiteLLM Tool Schema definition."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "bash",
                    "description": (
                        "Execute a shell command inside the project workspace "
                        "(e.g. running tests, linters, or build scripts) and return its trimmed output."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The shell command to run",
                            },
                        },
                        "required": ["command"],
                    },
                },
            },
        ]

    def _is_command_safe(self, command: str) -> tuple[bool, str]:
        """Validiert den Befehl auf versuchte System- und Verzeichnis-Ausbrüche."""
        # 1. Check auf sensible Systemverzeichnisse
        match = BLOCKED_SYSTEM_PATHS.search(command)
        if match:
            blocked_dir = match.group(1)
            return (
                False,
                f"Security Error: Access to system directory '{blocked_dir}' is"
                " forbidden. Commands must operate strictly within the project"
                " workspace.",
            )

        # 2. Check auf Path Traversal
        if DANGEROUS_TRAVERSAL.search(command):
            return (
                False,
                "Security Error: Path traversal outside the workspace ('../../') is"
                " forbidden.",
            )

        return True, ""

    async def execute(self, command: str) -> str:
        """Executes a command in the active environment and returns a JSON result."""
        clean_cmd = command.strip()

        # 1. Sicherheits-Check: Systemverzeichnisse abfangen
        match = BLOCKED_SYSTEM_PATHS.search(clean_cmd)
        if match:
            blocked_dir = match.group(1)
            error_msg = (
                f"Security Error: Access to system directory '{blocked_dir}' is"
                " forbidden. Commands must operate strictly within the project"
                " workspace."
            )
            return json.dumps(
                {
                    "success": False,
                    "exit_code": 126,
                    "output": error_msg,
                    "stdout": "",
                    "stderr": error_msg,
                },
                ensure_ascii=False,
            )

        # 2. Sicherheits-Check: Path Traversal abfangen
        if DANGEROUS_TRAVERSAL.search(clean_cmd):
            error_msg = (
                "Security Error: Path traversal outside the workspace ('../../') is"
                " forbidden. Commands must operate strictly within the project"
                " workspace."
            )
            return json.dumps(
                {
                    "success": False,
                    "exit_code": 126,
                    "output": error_msg,
                    "stdout": "",
                    "stderr": error_msg,
                },
                ensure_ascii=False,
            )

        # 3. Befehlsausführung in der Sandbox
        result = await self.sandbox.current_env.run(
            command=clean_cmd, timeout=self.timeout
        )
        exit_code = result.get("exit_code", 0)

        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")

        # 4. Output-Pruning
        pruned_stdout, pruned_stderr = prune_output(stdout, stderr, exit_code)

        if "stdout" in result:
            result["stdout"] = pruned_stdout
        if "stderr" in result:
            result["stderr"] = pruned_stderr

        if "output" in result:
            pruned_output, _ = prune_output(result["output"], "", exit_code)
            result["output"] = pruned_output

        return json.dumps(result, ensure_ascii=False)
