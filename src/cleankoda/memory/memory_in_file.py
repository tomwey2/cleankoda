import json
from pathlib import Path
from typing import Any

from cleankoda.memory.memory import Memory


class MemoryInFile(Memory):
    """File-persisted memory handler for LLM chat conversations.

    Extends `Memory` to automatically synchronize conversation history with a formatted
    JSON log file on disk upon every message modification.
    """

    def __init__(
        self,
        file: Path | str,
        system_prompt: str | None = None,
        initial_messages: list[dict[str, Any] | Any] | None = None,
    ) -> None:
        """Initializes MemoryInFile with file persistence support.

        If a file path is provided and the file already exists on disk, it is deleted and
        re-initialized fresh for the new session.

        Args:
            file: file path to save memory state in JSON format.
            system_prompt: Optional initial system prompt string.
            initial_messages: Optional list of initial messages.
        """
        self._file: Path= Path(file)
        if self._file and self._file.parent:
            self._file.parent.mkdir(parents=True, exist_ok=True)

        self._messages: list[dict[str, Any] | Any] = []
        if not self.load_memory():
            super().__init__(system_prompt=system_prompt, initial_messages=initial_messages)
        elif system_prompt:
            has_system = any(
                (isinstance(m, dict) and m.get("role") == "system")
                or getattr(m, "role", None) == "system"
                for m in self._messages
            )
            if not has_system:
                self._messages.insert(0, {"role": "system", "content": system_prompt})
                self._save_memory()


    def load_memory(self, file_path: Path | None = None) -> bool:
        """Loads chat messages from a JSON file into memory.

        Args:
            file_path: Optional path to the JSON log file. If omitted, uses the configured `file`.

        Returns:
            bool: True if messages were successfully loaded from the file, False otherwise.
        """
        target_file = Path(file_path) if file_path else self._file
        if not target_file or not target_file.is_file():
            return False
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                self._messages = data
                return True
        except Exception:
            pass
        return False

    @property
    def file(self) -> Path:
        """Returns the current log file path."""
        return self._file

    @file.setter
    def file(self, value: Path) -> None:
        """Sets or changes the log file path and triggers an immediate save.

        Args:
            value: New log file path (str or Path) or None to disable file persistence.
        """
        self._file = Path(value) if value else None
        if self._file and self._file.parent:
            self._file.parent.mkdir(parents=True, exist_ok=True)
        self._save_memory()

    def _save_memory(self) -> None:
        """Writes all stored messages to the log file as a formatted JSON array."""
        try:
            data = [self._message_to_dict(msg) for msg in self._messages]
            formatted_json = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            with open(self._file, "w", encoding="utf-8") as f:
                f.write(formatted_json + "\n")
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"MemoryInFile(messages_count={len(self._messages)}, log_file={self._file})"
