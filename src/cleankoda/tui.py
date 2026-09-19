import asyncio
import re

from prompt_toolkit.application import Application
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.filters import Condition, completion_is_selected, has_completions
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Float, FloatContainer, HSplit
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from cleankoda.agent import Agent
from cleankoda.commands import CommandContext, registry
from cleankoda.config import config
from cleankoda.state import get_active_issue
from cleankoda.statusline import statusline

BANNER = """
  ▄▄▄ █  ▄▄▄   ▄▄▄  ▄▄▄▄  █  ▄  ▄▄▄  ▄▄▄█  ▄▄▄
 █    █ █▄▄▄█  ▄▄▄█ █   █ █▄▀  █   █ █  █  ▄▄▄█
 ▀▄▄▄ █ ▀▄▄▄▄ ▀▄▄▄█ █   █ █ ▀▄ ▀▄▄▄▀ █▄▄█ ▀▄▄▄█
"""

TUI_STYLE = Style.from_dict({
    "completion-menu": "bg:#d0d0d0 #000000",
    "completion-menu.completion": "bg:#d0d0d0 #000000",
    "completion-menu.completion.current": "bg:#005f87 #ffffff noreverse bold",
    "completion-menu.meta": "bg:#d0d0d0 #555555",
    "completion-menu.meta.completion": "bg:#d0d0d0 #555555",
    "completion-menu.meta.completion.current": "bg:#005f87 #ffffff noreverse",
    "completion-menu.completion.current.meta": "bg:#005f87 #ffffff noreverse",
})


class SlashCommandCompleter(Completer):
    """Autocompleter for slash commands in the TUI input line."""

    def __init__(self, commands: dict[str, str] | None = None) -> None:
        self._commands = commands

    def _get_commands(self) -> dict[str, str]:
        if self._commands is not None:
            return self._commands
        return {f"/{cmd.name}": cmd.description for cmd in registry.list_commands()}

    def get_completions(self, document, complete_event):
        text_before_cursor = document.text_before_cursor

        if text_before_cursor.startswith("/sandbox "):
            parts = text_before_cursor.split()
            word = parts[-1] if len(parts) > 1 and not text_before_cursor.endswith(" ") else ""
            word_lower = word.lower()
            if "off".startswith(word_lower):
                yield Completion(
                    text="off",
                    start_position=-len(word),
                    display="off",
                    display_meta="Sandbox deaktivieren (HostRunner)",
                )
            return

        if text_before_cursor.endswith((" ", "\t", "\n")):
            word = ""
        else:
            words = text_before_cursor.split()
            word = words[-1] if words else text_before_cursor

        if not word.startswith("/"):
            return

        commands_map = self._get_commands()
        word_lower = word.lower()
        for cmd, desc in commands_map.items():
            if cmd.lower().startswith(word_lower):
                yield Completion(
                    text=cmd,
                    start_position=-len(word),
                    display=cmd,
                    display_meta=desc,
                )


class ChatLexer(Lexer):
    """Lexer that styles Markdown formatting and Rich markup tags in history_area."""

    def lex_document(self, document):
        lines = document.lines
        num_lines = len(lines)

        in_code_block = [False] * num_lines
        code = False
        for idx, line in enumerate(lines):
            if line.strip().startswith("```"):
                code = not code
                in_code_block[idx] = True
            else:
                in_code_block[idx] = code

        pattern = re.compile(
            r'(\[(\w+)\b[^\]]*\](.*?)\[/\2\])|'
            r'(\*\*(.*?)\*\*)|'
            r'(__([^_]+)__)|'
            r'(\*(.*?)\*)|'
            r'(_([^_]+)_)|'
            r'(`([^`]+)`)|'
            r'(\[(.*?)\]\((.*?)\))'
        )

        def parse_line_tokens(line: str, default_style: str = ""):
            result = []
            pos = 0
            for match in pattern.finditer(line):
                start, end = match.span()
                if start > pos:
                    result.append((default_style, line[pos:start]))

                full_match = match.group(1)

                rich_tag_color = match.group(2)
                rich_tag_content = match.group(3)
                bold_star = match.group(5)
                bold_under = match.group(7)
                italic_star = match.group(9)
                italic_under = match.group(11)
                code_content = match.group(13)
                link_text = match.group(15)

                if rich_tag_color:
                    style = f"fg:ansi{rich_tag_color}" if rich_tag_color != "bold" else "bold"
                    if default_style:
                        style = f"{default_style} {style}"
                    result.append((style, rich_tag_content))
                elif bold_star is not None or bold_under is not None:
                    txt = bold_star if bold_star is not None else bold_under
                    style = "bold" if not default_style else f"{default_style} bold"
                    result.append((style, txt))
                elif italic_star is not None or italic_under is not None:
                    txt = italic_star if italic_star is not None else italic_under
                    style = "italic" if not default_style else f"{default_style} italic"
                    result.append((style, txt))
                elif code_content is not None:
                    style = "fg:ansicyan"
                    result.append((style, code_content))
                elif link_text is not None:
                    style = "underline fg:ansiblue"
                    result.append((style, link_text))
                else:
                    result.append((default_style, full_match))

                pos = end

            if pos < len(line):
                result.append((default_style, line[pos:]))

            return result if result else [(default_style, "")]

        def get_line(lineno: int):
            if lineno >= num_lines:
                return [("", "")]

            line = lines[lineno]

            if in_code_block[lineno]:
                if line.strip().startswith("```"):
                    return [("bold fg:ansicyan", line)]
                return [("fg:ansicyan", line)]

            if line.startswith(">"):
                return parse_line_tokens(line, default_style="bold")

            if line.startswith("#"):
                return [("bold fg:ansiyellow", line)]

            if line.lstrip().startswith(("- ", "* ", "• ")):
                return parse_line_tokens(line)

            return parse_line_tokens(line)

        return get_line


class TUI:
    """Terminal User Interface application for cleankoda cli."""

    def __init__(self, agent: Agent) -> None:
        self.agent = agent
        self.showing_shortcuts = False
        self.is_processing = False
        self._cancel_event: asyncio.Event | None = None

        self.history_area = TextArea(
            text=BANNER
            + " Welcome to cleankoda!\n"
            + " The coding agent for clean code software development.\n"
            + f" Workspace: {config.workspace}\n"
            + ("─" * 60)
            + "\n",
            scrollbar=True,
            read_only=True,
            wrap_lines=True,
            focusable=False,
            lexer=ChatLexer(),
        )

        self.input_field = TextArea(
            height=3,
            prompt="> ",
            multiline=False,
            wrap_lines=False,
            completer=SlashCommandCompleter(),
            complete_while_typing=True,
            auto_suggest=AutoSuggestFromHistory(),
        )

        self.status_line = TextArea(
            height=2,
            text=f"{self.get_session_status_text()}\nCtrl+O for shortcuts",
            multiline=True,
            wrap_lines=True,
        )

        self.root_container = HSplit([
            self.history_area,
            Frame(self.input_field),
            self.status_line,
        ])

        self.float_container = FloatContainer(
            content=self.root_container,
            floats=[
                Float(
                    content=CompletionsMenu(max_height=8, scroll_offset=1),
                    xcursor=True,
                    ycursor=True,
                )
            ],
        )
        self.layout = Layout(self.float_container, focused_element=self.input_field)

        self.kb = KeyBindings()
        self._register_keybindings()

        self.input_field.accept_handler = self._accept_handler

        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            full_screen=True,
            mouse_support=True,
            style=TUI_STYLE,
        )
        self.app.float_container = self.float_container
        self.app.tui = self

    def _get_bottom_toolbar_text(self) -> str:
        active = get_active_issue()
        if active:
            return f"[Issue: #{active.id} {active.title}]"
        return "[No active Issue]"

    def on_status_changed(self, status: str = "") -> None:
        self.update_status_line()
        try:
            if hasattr(self, "app") and self.app:
                self.app.invalidate()
        except Exception:
            pass

    @property
    def cancel_event(self) -> asyncio.Event:
        if self._cancel_event is None:
            self._cancel_event = asyncio.Event()
        return self._cancel_event

    def get_session_status_text(self) -> str:
        active = get_active_issue()
        issue_str = (
            f"[Issue: #{active.id} {active.title}]"
            if active
            else "[No active Issue]"
        )
        sb_image = self.agent.sandbox.get_sandbox_image()
        sb_status = "Sandbox: " + sb_image.name if sb_image and sb_image.id != "host" else "no Sandbox"
        return f"{issue_str} | Provider: {config.provider} | Model: {config.model} | Temp: {config.temperature} | {sb_status}"

    def update_status_line(self) -> None:
        session_text = self.get_session_status_text()
        if self.showing_shortcuts:
            self.status_line.window.height = 5
            self.status_line.text = (
                f"{session_text}\n"
                "Shortcuts & Help (ESC to close):\n"
                "• Enter   : Send message\n"
                "• Ctrl+C  : Exit application\n"
                "• Ctrl+Q  : Exit application"
            )
        else:
            active_status = statusline.get_combined_status()
            self.status_line.window.height = 2
            if active_status:
                self.status_line.text = f"{session_text}\n{active_status}"
            else:
                self.status_line.text = f"{session_text}\nCtrl+O for shortcuts"

    def _register_keybindings(self) -> None:
        @self.kb.add("c-c")
        @self.kb.add("c-q")
        def _exit(event):
            event.app.exit()

        @Condition
        def is_input_allowed() -> bool:
            return self.agent.is_busy()

        @self.kb.add("c-o", eager=True)
        def _show_shortcuts(event):
            self.showing_shortcuts = True
            self.input_field.read_only = True
            self.update_status_line()
            event.app.invalidate()

        @self.kb.add("escape", eager=True, filter=~is_input_allowed)
        def _handle_escape(event):
            if self.is_processing:
                self.cancel_event.set()
            if self.input_field.text.lstrip().startswith("/"):
                self.input_field.text = ""
            self.showing_shortcuts = False
            if not self.is_processing:
                self.input_field.read_only = False
            self.update_status_line()
            event.app.invalidate()

        @self.kb.add("enter", filter=(has_completions | completion_is_selected) & is_input_allowed)
        def _accept_completion(event):
            buff = event.current_buffer
            if buff.complete_state:
                completion = buff.complete_state.current_completion
                if completion is None and buff.complete_state.completions:
                    completion = buff.complete_state.completions[0]
                if completion:
                    buff.apply_completion(completion)
                buff.complete_state = None

    def _accept_handler(self, buff) -> None:
        if self.input_field.read_only or self.is_processing:
            return
        user_input = self.input_field.text.strip()
        if not user_input:
            return

        self.input_field.text = ""
        asyncio.create_task(self._safe_stream_response(user_input))

    async def _safe_stream_response(self, user_text: str) -> None:
        self.is_processing = True
        self.input_field.read_only = True
        try:
            await self.stream_response(user_text)
        except Exception as e:
            self.history_area.text += f"\n\n[Error]: {e}\n"
            self.history_area.buffer.cursor_position = len(self.history_area.text)
        finally:
            self.is_processing = False
            self.showing_shortcuts = False
            self.input_field.read_only = False
            self.input_field.text = ""
            self.input_field.buffer.cursor_position = 0
            self.update_status_line()
            try:
                self.app.layout.focus(self.input_field)
            except Exception:
                pass
            self.app.invalidate()
            await asyncio.sleep(0.01)
            try:
                self.app.layout.focus(self.input_field)
            except Exception:
                pass
            self.app.invalidate()

    async def stream_response(self, user_text: str) -> None:
        if user_text.startswith("/"):
            ctx = CommandContext(memory=self.agent.memory, app=self.app, agent=self.agent)
            result = await registry.dispatch_async(user_text, ctx)
            if result.output:
                self.history_area.text += f"\n\n[System]: {result.output}\n"
                self.history_area.buffer.cursor_position = len(self.history_area.text)
                self.app.invalidate()
            self.update_status_line()
            if result.should_exit:
                self.app.exit()
            return

        formatted_user = "\n".join(f"> {line}" for line in user_text.splitlines()) if user_text else f"> {user_text}"
        self.history_area.text += f"\n\n{formatted_user}\n\n  "
        self.history_area.buffer.cursor_position = len(self.history_area.text)
        self.app.invalidate()

        self.agent.memory.add_user(user_text)

        self.cancel_event.clear()

        async for chunk in self.agent.run(
            cancel_event=self.cancel_event,
        ):
            indented_chunk = chunk.replace("\n", "\n  ")
            self.history_area.text += indented_chunk
            self.history_area.buffer.cursor_position = len(self.history_area.text)
            self.app.invalidate()

    def run(self) -> None:
        self.update_status_line()
        try:
            asyncio.run(self.app.run_async())
        finally:
            if self.agent.sandbox:
                self.agent.sandbox.stop()


def run_tui(agent: Agent) -> None:
    """Start the interactive TUI application with the provided Agent instance."""
    tui = TUI(agent)
    statusline.on_change = tui.on_status_changed
    tui.run()
