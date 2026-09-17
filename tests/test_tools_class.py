import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from cleankoda.sandbox import Sandbox
from cleankoda.tools import ToolRegistry


class TestToolsClass(unittest.TestCase):

    def test_tools_workspace_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir).resolve()
            sandbox = Sandbox(default_image_id=None, workspace=ws_path)
            tools = ToolRegistry(sandbox=sandbox)

            self.assertEqual(tools.sandbox.workspace, ws_path)
            self.assertEqual(tools.fs.workspace_root, ws_path)

    def test_tools_file_operations(self):
        async def _test():
            with tempfile.TemporaryDirectory() as tmpdir:
                ws_path = Path(tmpdir).resolve()
                sandbox = Sandbox(default_image_id=None, workspace=ws_path)
                tools = ToolRegistry(sandbox=sandbox)

                # Test write_file
                mock_call_write = MagicMock()
                mock_call_write.function.name = "write_file"
                mock_call_write.function.arguments = '{"path": "hello.txt", "content": "Hello Tools"}'

                res_write = await tools.run_tool(mock_call_write)
                self.assertIn("Successfully wrote", res_write)

                # Test read_file
                mock_call_read = MagicMock()
                mock_call_read.function.name = "read_file"
                mock_call_read.function.arguments = '{"path": "hello.txt"}'

                res_read = await tools.run_tool(mock_call_read)
                self.assertEqual(res_read, "Hello Tools")

                # Test list_dir
                mock_call_list = MagicMock()
                mock_call_list.function.name = "list_dir"
                mock_call_list.function.arguments = '{"path": "."}'

                res_list = await tools.run_tool(mock_call_list)
                self.assertIn("hello.txt", res_list)

        asyncio.run(_test())

    def test_tools_schemas(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir).resolve()
            sandbox = Sandbox(default_image_id=None, workspace=ws_path)
            tools = ToolRegistry(sandbox=sandbox)

            schemas = tools.get_schemas()
            self.assertIsInstance(schemas, list)
            self.assertTrue(len(schemas) > 0)


if __name__ == "__main__":
    unittest.main()
