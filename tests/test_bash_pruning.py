import asyncio
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, MagicMock

from cleankoda.sandbox import Sandbox
from cleankoda.tools.bash import Bash, prune_output


class TestBashPruning(unittest.TestCase):

    def setUp(self):
        self.workspace = Path.cwd()
        self.sandbox = Sandbox(default_image_id=None, workspace=self.workspace)

    def test_default_timeout(self):
        bash = Bash(sandbox=self.sandbox)
        self.assertEqual(bash.timeout, 120)

    def test_schema_description(self):
        bash = Bash(sandbox=self.sandbox)
        schemas = bash.schema
        self.assertEqual(len(schemas), 1)
        desc = schemas[0]["function"]["description"]
        self.assertEqual(
            desc,
            "Execute a shell command inside the project workspace (e.g. running tests, linters, or build scripts) and return its trimmed output.",
        )

    def test_prune_output_success_short(self):
        stdout = "\n".join([f"line {i}" for i in range(50)])
        pruned_stdout, _ = prune_output(stdout, "", exit_code=0)
        self.assertEqual(pruned_stdout, stdout)

    def test_prune_output_success_long(self):
        lines = [f"line {i}" for i in range(100)]
        stdout = "\n".join(lines)
        pruned_stdout, _ = prune_output(stdout, "", exit_code=0)
        res_lines = pruned_stdout.splitlines()

        self.assertEqual(len(res_lines), 51)  # 15 + 1 notice + 35
        self.assertEqual(res_lines[0], "line 0")
        self.assertEqual(res_lines[14], "line 14")
        self.assertEqual(res_lines[15], "[... 50 lines omitted ...]")
        self.assertEqual(res_lines[16], "line 65")
        self.assertEqual(res_lines[-1], "line 99")

    def test_prune_output_failure_short(self):
        stdout = "\n".join([f"line {i}" for i in range(30)])
        pruned_stdout, _ = prune_output(stdout, "", exit_code=1)
        self.assertEqual(pruned_stdout, stdout)

    def test_prune_output_failure_long_with_errors(self):
        lines = []
        for i in range(100):
            if i in (5, 10):
                lines.append(f"line {i}: Traceback (most recent call last): ERROR occurred")
            else:
                lines.append(f"line {i}")
        stdout = "\n".join(lines)

        pruned_stdout, _ = prune_output(stdout, "", exit_code=1)
        res_lines = pruned_stdout.splitlines()

        self.assertEqual(res_lines[0], "line 5: Traceback (most recent call last): ERROR occurred")
        self.assertEqual(res_lines[1], "line 10: Traceback (most recent call last): ERROR occurred")
        self.assertEqual(res_lines[2], "[... 58 lines omitted ...]")
        self.assertEqual(res_lines[3], "line 60")
        self.assertEqual(res_lines[-1], "line 99")

    def test_prune_output_failure_long_without_errors(self):
        lines = [f"line {i}" for i in range(100)]
        stdout = "\n".join(lines)
        pruned_stdout, _ = prune_output(stdout, "", exit_code=1)
        res_lines = pruned_stdout.splitlines()

        self.assertEqual(res_lines[0], "[... 60 lines omitted ...]")
        self.assertEqual(res_lines[1], "line 60")
        self.assertEqual(res_lines[-1], "line 99")

    def test_prune_output_hard_character_limit(self):
        long_line = "A" * 10000
        pruned_stdout, _ = prune_output(long_line, "", exit_code=0)
        self.assertEqual(len(pruned_stdout), 8000)

    def test_bash_execute_pruning(self):
        bash = Bash(sandbox=self.sandbox)
        mock_env = MagicMock()
        long_output = "\n".join([f"output line {i}" for i in range(100)])
        mock_env.run = AsyncMock(return_value={
            "success": True,
            "exit_code": 0,
            "output": long_output,
            "stdout": long_output,
            "stderr": "",
        })
        self.sandbox.current_env = mock_env

        async def _run():
            result_json = await bash.execute("pytest")
            data = json.loads(result_json)
            self.assertIn("[... 50 lines omitted ...]", data["output"])
            self.assertIn("[... 50 lines omitted ...]", data["stdout"])

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
