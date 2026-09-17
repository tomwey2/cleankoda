import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from cleankoda.sandbox import Sandbox
from cleankoda.tools import BashCommand, ListDir, ReadFile, ToolRegistry, WriteFile


class TestToolsClass(unittest.TestCase):

    def test_tools_workspace_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws_path = Path(tmpdir).resolve()
            sandbox = Sandbox(default_image_id=None, workspace=ws_path)
            list_dir = ListDir(workspace=ws_path)
            read_file = ReadFile(workspace=ws_path)
            write_file = WriteFile(workspace=ws_path)
            bash_cmd = BashCommand(sandbox=sandbox)

            self.assertEqual(sandbox.workspace, ws_path)
            self.assertEqual(list_dir.workspace_root, ws_path)
            self.assertEqual(read_file.workspace_root, ws_path)
            self.assertEqual(write_file.workspace_root, ws_path)
            self.assertEqual(bash_cmd.sandbox, sandbox)

    def test_tools_file_operations(self):
        async def _test():
            with tempfile.TemporaryDirectory() as tmpdir:
                ws_path = Path(tmpdir).resolve()
                sandbox = Sandbox(default_image_id=None, workspace=ws_path)
                tools_list = [
                    ListDir(workspace=ws_path),
                    ReadFile(workspace=ws_path),
                    WriteFile(workspace=ws_path),
                    BashCommand(sandbox=sandbox),
                ]
                tools = ToolRegistry(tools=tools_list)

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
            tools_list = [
                ListDir(workspace=ws_path),
                ReadFile(workspace=ws_path),
                WriteFile(workspace=ws_path),
                BashCommand(sandbox=sandbox),
            ]
            tools = ToolRegistry(tools=tools_list)

            schemas = tools.get_schemas()
            self.assertIsInstance(schemas, list)
            self.assertEqual(len(schemas), 4)


if __name__ == "__main__":
    unittest.main()
