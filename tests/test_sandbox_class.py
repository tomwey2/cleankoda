import tempfile
import unittest
from pathlib import Path

from cleankoda.sandbox import Sandbox


class TestSandboxClass(unittest.TestCase):

    def test_sandbox_workspace_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir).resolve()
            sandbox = Sandbox(default_image_id=None, workspace=ws_path)

            self.assertEqual(sandbox.workspace, ws_path)
            self.assertEqual(sandbox.current_env.workspace_path, ws_path)

    def test_sandbox_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir).resolve()
            sandbox = Sandbox(default_image_id=None, workspace=ws_path)
            self.assertEqual(sandbox.get_sandbox_image().id, "host")

    def test_sandbox_start_async_docker_trigger(self):
        import asyncio
        from unittest.mock import AsyncMock, patch

        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir).resolve()
            sandbox = Sandbox(default_image_id="docker:latest", workspace=ws_path)

            async def _test():
                with patch.object(sandbox, "switch_environment", new_callable=AsyncMock) as mock_switch:
                    await sandbox.start_async()
                    mock_switch.assert_called_once_with("docker:latest")

            asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
