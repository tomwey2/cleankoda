import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from prompt_toolkit.buffer import CompletionState
from prompt_toolkit.completion import Completion
from prompt_toolkit.document import Document

from cleankoda.agent import Agent
from cleankoda.commands import registry
from cleankoda.memory import Memory
from cleankoda.sandbox import Sandbox
from cleankoda.statusline import statusline
from cleankoda.tools import BashCommand, ListDir, ReadFile, WriteFile
from cleankoda.tui import ChatLexer, SlashCommandCompleter, TUI, TUI_STYLE


class TestSlashCommandCompleter(unittest.TestCase):

    def setUp(self):
        self.completer = SlashCommandCompleter()

    def test_trigger_on_slash(self):
        doc = Document("/", 1)
        completions = list(self.completer.get_completions(doc, None))
        texts = [c.text for c in completions]
        self.assertIn("/plan", texts)
        self.assertIn("/provider", texts)
        self.assertIn("/model", texts)
        self.assertIn("/clear", texts)
        self.assertIn("/help", texts)
        self.assertIn("/exit", texts)
        for c in completions:
            self.assertEqual(c.start_position, -1)

    def test_prefix_filtering_case_insensitive(self):
        doc = Document("/PROV", 5)
        completions = list(self.completer.get_completions(doc, None))
        self.assertEqual(len(completions), 1)
        self.assertEqual(completions[0].text, "/provider")
        self.assertEqual(completions[0].display_meta_text, registry._commands["provider"].description)
        self.assertEqual(completions[0].start_position, -5)

    def test_no_completion_without_slash(self):
        doc = Document("hello world", 11)
        completions = list(self.completer.get_completions(doc, None))
        self.assertEqual(len(completions), 0)

    def test_no_completion_after_trailing_space(self):
        doc = Document("/exit ", 6)
        completions = list(self.completer.get_completions(doc, None))
        self.assertEqual(len(completions), 0)


class TestChatLexer(unittest.TestCase):

    def test_rich_color_tags(self):
        doc = Document("[yellow]LLM startup aborted.[/yellow]\n[green]✔ Model ready.[/green]", 0)
        lexer = ChatLexer()
        get_line = lexer.lex_document(doc)

        line0 = get_line(0)
        self.assertEqual(line0, [("fg:ansiyellow", "LLM startup aborted.")])

        line1 = get_line(1)
        self.assertEqual(line1, [("fg:ansigreen", "✔ Model ready.")])

    def test_markdown_inline(self):
        doc = Document("Hello **bold** and *italic* and `code` and [link](http://test)", 0)
        lexer = ChatLexer()
        get_line = lexer.lex_document(doc)

        line0 = get_line(0)
        styles_and_texts = [(style, text) for style, text in line0]
        self.assertEqual(
            styles_and_texts,
            [
                ("", "Hello "),
                ("bold", "bold"),
                ("", " and "),
                ("italic", "italic"),
                ("", " and "),
                ("fg:ansicyan", "code"),
                ("", " and "),
                ("underline fg:ansiblue", "link"),
            ],
        )

    def test_headers_and_code_blocks(self):
        doc = Document("# Header 1\n```python\nprint('hello')\n```", 0)
        lexer = ChatLexer()
        get_line = lexer.lex_document(doc)

        self.assertEqual(get_line(0), [("bold fg:ansiyellow", "# Header 1")])
        self.assertEqual(get_line(1), [("bold fg:ansicyan", "```python")])
        self.assertEqual(get_line(2), [("fg:ansicyan", "print('hello')")])
        self.assertEqual(get_line(3), [("bold fg:ansicyan", "```")])


class TestTUIStyleAndConfig(unittest.TestCase):

    def test_tui_style_keys(self):
        self.assertTrue(len(TUI_STYLE.style_rules) > 0)


class TestTUIEscapeKeybinding(unittest.TestCase):

    def test_escape_clears_slash_command_prompt(self):
        memory = Memory(system_prompt="Test")
        sb = Sandbox(default_image_id=None, workspace=Path.cwd())
        tools = [
            ListDir(workspace=Path.cwd()),
            ReadFile(workspace=Path.cwd()),
            WriteFile(workspace=Path.cwd()),
            BashCommand(sandbox=sb),
        ]
        agent = Agent(memory=memory, tools=tools, sandbox=sb)
        tui = TUI(agent)
        tui.input_field.text = "/model"

        # Trigger escape keybinding handler
        escape_binding = next(b for b in tui.kb.bindings if b.keys[0].value == "escape" or b.keys[0] == "escape")
        escape_binding.handler(MagicMock())
        self.assertEqual(tui.input_field.text, "")

    def test_escape_preserves_regular_prompt(self):
        memory = Memory(system_prompt="Test")
        sb = Sandbox(default_image_id=None, workspace=Path.cwd())
        tools = [
            ListDir(workspace=Path.cwd()),
            ReadFile(workspace=Path.cwd()),
            WriteFile(workspace=Path.cwd()),
            BashCommand(sandbox=sb),
        ]
        agent = Agent(memory=memory, tools=tools, sandbox=sb)
        tui = TUI(agent)
        tui.input_field.text = "Hello world"

        # Trigger escape keybinding handler
        escape_binding = next(b for b in tui.kb.bindings if b.keys[0].value == "escape" or b.keys[0] == "escape")
        escape_binding.handler(MagicMock())
        self.assertEqual(tui.input_field.text, "Hello world")


class TestTUIEnterCompletionKeybinding(unittest.TestCase):

    @patch("prompt_toolkit.buffer.get_app")
    def test_enter_applies_completion_without_executing(self, mock_get_app):
        mock_app = MagicMock()
        def _close_coro(coro):
            if hasattr(coro, "close"):
                coro.close()
        mock_app.create_background_task.side_effect = _close_coro
        mock_get_app.return_value = mock_app

        memory = Memory(system_prompt="Test")
        sb = Sandbox(default_image_id=None, workspace=Path.cwd())
        tools = [
            ListDir(workspace=Path.cwd()),
            ReadFile(workspace=Path.cwd()),
            WriteFile(workspace=Path.cwd()),
            BashCommand(sandbox=sb),
        ]
        agent = Agent(memory=memory, tools=tools, sandbox=sb)
        tui = TUI(agent)
        tui.input_field.text = "/m"
        tui.input_field.buffer.cursor_position = 2

        comp = Completion("/model", start_position=-2, display="/model")
        state = CompletionState(original_document=tui.input_field.buffer.document, completions=[comp])
        tui.input_field.buffer.complete_state = state

        # Find the enter keybinding registered for completions
        enter_binding = next(b for b in tui.kb.bindings if any(getattr(k, "value", k) in ("c-m", "enter") for k in b.keys))
        mock_event = MagicMock()
        mock_event.current_buffer = tui.input_field.buffer
        enter_binding.handler(mock_event)

        # Verify prompt text is updated to "/model" and complete_state is None
        self.assertEqual(tui.input_field.text, "/model")
        self.assertIsNone(tui.input_field.buffer.complete_state)


class TestTUIStatusManager(unittest.TestCase):

    def test_status_manager_updates_status_line(self):
        memory = Memory(system_prompt="Test")
        sb = Sandbox(default_image_id=None, workspace=Path.cwd())
        tools = [
            ListDir(workspace=Path.cwd()),
            ReadFile(workspace=Path.cwd()),
            WriteFile(workspace=Path.cwd()),
            BashCommand(sandbox=sb),
        ]
        agent = Agent(memory=memory, tools=tools, sandbox=sb)
        tui = TUI(agent)
        statusline.on_change = tui.on_status_changed
        mock_app = MagicMock()
        tui.app = mock_app

        # Initially default status line text
        self.assertIn("[No active Issue]", tui.status_line.text)

        # Setting status via statusline automatically updates status line
        try:
            statusline.set("sandbox", "Sandbox: Startet (docker:latest)...")
            self.assertIn("Sandbox: Startet (docker:latest)...", tui.status_line.text)
            mock_app.invalidate.assert_called()

            # Multiple slots are combined
            statusline.set("llm", "LLM Cold Start: Versuch 1/10 (10s gewartet)")
            self.assertIn(
                "Sandbox: Startet (docker:latest)... | LLM Cold Start: Versuch 1/10 (10s gewartet)",
                tui.status_line.text,
            )

            # Clearing slots reverts back to active issue status when empty
            statusline.clear("sandbox")
            statusline.clear("llm")
            self.assertIn("[No active Issue]", tui.status_line.text)
        finally:
            statusline.on_change = None


if __name__ == "__main__":
    unittest.main()
