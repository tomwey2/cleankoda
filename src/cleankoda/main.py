import argparse
import asyncio
import sys
from pathlib import Path

from cleankoda.agent import Agent
from cleankoda.commands import CommandContext, registry
from cleankoda.config import config
from cleankoda.memory import MemoryInFile
from cleankoda.sandbox import Sandbox
from cleankoda.sandbox.config import DEFAULT_IMAGE
from cleankoda.state import SessionState, get_session_state
from cleankoda.tui import run_tui
from cleankoda.tools import Glob, ReadFile, WriteFile, ListDir, Bash
from cleankoda.prompts import SYSTEM_PROMPT


def set_workspace(workspace: Path) -> None:
    if workspace != config.workspace:
        config.workspace = workspace
        config.save()


def headless_status_callback(state: SessionState) -> None:
    status = state.get_combined_status()
    if status:
        print(f"▶ {status}", file=sys.stderr)


async def _run_headless_agent(
    agent: Agent,
    prompt_text: str,
) -> int:
    if agent.sandbox:
        await agent.sandbox.start_async()
    agent.memory.add_user(prompt_text)
    get_session_state().subscribe(headless_status_callback)
    try:
        async for chunk in agent.run():
            print(chunk, end="", flush=True)
        print()
        return 0
    except Exception as e:
        print(f"Error running agent: {e}", file=sys.stderr)
        return 1


def run_headless(
    agent: Agent,
    prompt_text: str,
) -> int:
    """Execute the prompt in headless mode without TUI.

    Returns exit code 0 on success, or 1 on failure.
    """
    try:
        # Slash-Command Check
        if prompt_text.startswith("/"):
            ctx = CommandContext(memory=agent.memory, agent=agent)

            async def _run_slash():
                if agent.sandbox:
                    await agent.sandbox.start_async()
                return await registry.dispatch_async(prompt_text, ctx)

            result = asyncio.run(_run_slash())
            if result.output:
                print(result.output)
            return 0

        return asyncio.run(_run_headless_agent(agent, prompt_text))
    finally:
        if agent.sandbox:
            agent.sandbox.stop()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="cleankoda CLI")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--tui", action="store_true", help="Force TUI mode")
    mode_group.add_argument("--headless", action="store_true", help="Force headless mode")
    parser.add_argument("prompt_pos", nargs="*", help="Optionaler Prompt (Headless)")
    parser.add_argument("-p", "--prompt", help="Prompt für den Headless-Modus")
    parser.add_argument("-ws", "--workspace", type=Path, help="Set workspace directory")

    args = parser.parse_args(argv)

    prompt_parts = args.prompt_pos if args.prompt_pos else []
    pos_prompt = " ".join(prompt_parts).strip() if prompt_parts else None
    prompt = args.prompt or pos_prompt

    piped_input = None
    if not sys.stdin.isatty():
        try:
            piped_input = sys.stdin.read().strip()
        except OSError as err:
            print(f"Warning: Could not read standard input: {err}", file=sys.stderr)

    if prompt and piped_input:
        final_prompt = f"{prompt}\n\n{piped_input}"
    else:
        final_prompt = prompt or piped_input

    if args.workspace:
        ws_path = args.workspace.expanduser().resolve()
        if not ws_path.exists():
            print(f"Error: Workspace directory '{args.workspace}' does not exist.", file=sys.stderr)
            sys.exit(1)
        set_workspace(ws_path)
    else:
        set_workspace(Path.cwd())

    sandbox = Sandbox(
        workspace=config.workspace,
        default_image_id=config.sandbox if config.sandbox else DEFAULT_IMAGE,
    )

    memory = MemoryInFile(file=".agents/memory.json", system_prompt=SYSTEM_PROMPT)

    agent = Agent(
        memory=memory,
        tools=[
            Glob(workspace=config.workspace),
            ReadFile(workspace=config.workspace),
            WriteFile(workspace=config.workspace),
            Bash(sandbox),
            ListDir(workspace=config.workspace)],
        sandbox=sandbox
    )

    if args.headless or final_prompt is not None:
        if not final_prompt:
            print("Error: Headless mode requires a prompt argument or piped standard input.", file=sys.stderr)
            sys.exit(1)
        code = run_headless(agent, final_prompt)
        if isinstance(code, int) and code != 0:
            sys.exit(code)
    else:
        run_tui(agent)


if __name__ == "__main__":
    main()
