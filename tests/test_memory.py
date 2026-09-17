from cleankoda.memory import MemoryInFile
import json
import tempfile
import unittest
from pathlib import Path
from cleankoda.memory import Memory


class TestMemory(unittest.TestCase):

    def test_init_without_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "memory.json"
            mem = MemoryInFile(system_prompt="Test System Prompt", file=file_path)
            self.assertEqual(len(mem), 1)
            self.assertEqual(mem[0], {"role": "system", "content": "Test System Prompt"})
            self.assertTrue(file_path.exists())

    def test_init_with_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "memory.json"
            saved_messages = [
                {"role": "system", "content": "Saved System Prompt"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ]
            file_path.write_text(json.dumps(saved_messages), encoding="utf-8")

            mem = MemoryInFile(system_prompt="New System Prompt", file=file_path)
            self.assertEqual(len(mem), 3)
            self.assertEqual(mem.messages, saved_messages)

    def test_init_with_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "memory.json"
            file_path.write_text("invalid json content", encoding="utf-8")

            mem = MemoryInFile(system_prompt="Fallback Prompt", file=file_path)
            self.assertEqual(len(mem), 1)
            self.assertEqual(mem[0]["content"], "Fallback Prompt")

    def test_load_memory_explicit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "memory.json"
            mem = MemoryInFile(system_prompt="Initial", file=file_path)
            self.assertEqual(len(mem), 1)

            saved_messages = [
                {"role": "system", "content": "System"},
                {"role": "user", "content": "User message"},
            ]
            file_path.write_text(json.dumps(saved_messages), encoding="utf-8")

            loaded = mem.load_memory()
            self.assertTrue(loaded)
            self.assertEqual(len(mem), 2)
            self.assertEqual(mem.messages, saved_messages)


if __name__ == "__main__":
    unittest.main()
