import asyncio
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from cleankoda.sandbox import (
    DockerEnvironment,
    HostEnvironment,
    Sandbox,
)
from cleankoda.tools.bash import Bash


class TestSandboxPackage(unittest.TestCase):

    def setUp(self):
        self.workspace = Path.cwd()

    def test_host_sandbox_execution(self):
        host_env = HostEnvironment(workspace_path=self.workspace)

        async def _run():
            res = await host_env.run("echo 'Hello World'")
            self.assertTrue(res["success"])
            self.assertEqual(res["exit_code"], 0)
            self.assertEqual(res["output"], "Hello World")

        asyncio.run(_run())

    def test_host_sandbox_truncation(self):
        host_env = HostEnvironment(workspace_path=self.workspace, max_output_chars=50)

        async def _run():
            res = await host_env.run("python3 -c \"print('A' * 100)\"")
            self.assertTrue(res["success"])
            self.assertIn("[... 50 Zeichen gekürzt / Output Truncated ...]", res["output"])

        asyncio.run(_run())

    @patch("cleankoda.sandbox.sandbox.DockerEnvironment")
    def test_sandbox_switching(self, mock_docker_sandbox):
        def _make_mock(workspace_path, image):
            mock = MagicMock()
            mock.image = image

            async def _fake_start_async():
                pass

            mock.start_async = _fake_start_async
            return mock

        mock_docker_sandbox.side_effect = _make_mock

        async def _test():
            sb = Sandbox(default_image_id=None, workspace=self.workspace)
            self.assertIsInstance(sb.current_env, HostEnvironment)
            self.assertEqual(sb.get_sandbox_image().id, "host")

            status_msg_off = await sb.switch_environment(None)
            self.assertIn("Sandbox disabled", status_msg_off)
            self.assertEqual(sb.get_sandbox_image().id, "host")

        asyncio.run(_test())

    def test_bash_command_tool(self):
        sb = Sandbox(default_image_id=None, workspace=self.workspace)
        bash_tool = Bash(sandbox=sb)

        async def _run():
            output_json = await bash_tool.execute("echo 'Tool Test'")
            data = json.loads(output_json)
            self.assertTrue(data["success"])
            self.assertEqual(data["output"], "Tool Test")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
