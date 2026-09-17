from cleankoda.memory.memory_in_file import MemoryInFile
import unittest
import tempfile
from pathlib import Path

from cleankoda.commands import CommandContext, registry
from cleankoda.memory import Memory


class TestCommandRegistry(unittest.TestCase):

    def test_auto_loaded_commands_present(self):
        cmds = registry.list_commands()
        cmd_names = {c.name for c in cmds}
        self.assertIn("exit", cmd_names)
        self.assertIn("clear", cmd_names)
        self.assertIn("model", cmd_names)
        self.assertIn("help", cmd_names)

    def test_cmd_exit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "memory.json"
            memory = MemoryInFile(system_prompt="Test System Prompt", file=file_path)
            ctx = CommandContext(memory=memory)

            res = registry.dispatch("/exit", ctx)
            self.assertTrue(res.should_exit)
            self.assertEqual(res.output, "Goodbye!")

            # Test alias
            res_alias = registry.dispatch("/q", ctx)
            self.assertTrue(res_alias.should_exit)

    def test_cmd_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "memory.json"
            memory = MemoryInFile(system_prompt="Test System Prompt", file=file_path)
            ctx = CommandContext(memory=memory)

            memory.add_user("Hello agent")
            self.assertEqual(len(memory.messages), 2)  # system + user

            res = registry.dispatch("/clear", ctx)
            self.assertEqual(res.output, "Conversation memory cleared.")
            self.assertEqual(len(memory.messages), 1)  # only system remains

    def test_cmd_help(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "memory.json"
            memory = MemoryInFile(system_prompt="Test System Prompt", file=file_path)
            ctx = CommandContext(memory=memory)

            res = registry.dispatch("/help", ctx)
            self.assertIn("Available Commands:", res.output)
            self.assertIn("/exit", res.output)
            self.assertIn("/clear", res.output)
            self.assertIn("/model", res.output)

    def test_unknown_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "memory.json"
            memory = MemoryInFile(system_prompt="Test System Prompt", file=file_path)
            ctx = CommandContext(memory=memory)

            res = registry.dispatch("/foobar", ctx)
            self.assertIn("Unknown command: '/foobar'", res.output)


if __name__ == "__main__":
    unittest.main()
