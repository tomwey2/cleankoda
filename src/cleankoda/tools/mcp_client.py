import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
import os
import sys
from typing import AsyncGenerator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def connect_mcp_server(
    command: str = sys.executable,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> tuple[AsyncExitStack, ClientSession]:
  """Connects to an MCP server via stdio transport and returns the exit stack and session."""
  args = list(args) if args else []

  # Falls ein Python-Skript gestartet wird, unbuffered mode (-u) erzwingen
  if ("python" in command or command == sys.executable) and "-u" not in args:
    args.insert(0, "-u")

  clean_env = {}
  for k, v in os.environ.items():
      if (
          k.startswith("PYDEVD_")
          or k.startswith("DEBUGPY_")
          or k == "PYTHONBREAKPOINT"
      ):
          continue
      if k == "PYTHONPATH" and ("debugpy" in v or "pydevd" in v):
          continue
      clean_env[k] = v

  merged_env = {
      **clean_env,
      "PYTHONUNBUFFERED": "1",
      "DEBUGPY_SUBPROCESS": "0",
      "PYDEVD_DISABLE_SUBPROCESS": "1",
      "PYDEVD_DO_NOT_TRACE": "1",
      **(env or {}),
  }

  server_params = StdioServerParameters(
      command=command,
      args=args,
      env=merged_env,
  )

  exit_stack = AsyncExitStack()
  try:
    read_stream, write_stream = await exit_stack.enter_async_context(
        stdio_client(server_params)
    )
    session = await exit_stack.enter_async_context(
        ClientSession(read_stream, write_stream)
    )

    # Schützt vor lautlosem Einfrieren, falls der Server hängt
    async with asyncio.timeout(timeout):
      await session.initialize()

    return exit_stack, session

  except TimeoutError:
    try:
      async with asyncio.timeout(2.0):
        await exit_stack.aclose()
    except Exception:
        pass
    raise TimeoutError(
        f"MCP server initialization timed out after {timeout}s (Command:"
        f" {command} {' '.join(args)})."
    )
  except Exception:
    try:
      async with asyncio.timeout(2.0):
        await exit_stack.aclose()
    except Exception:
        pass
    raise


@asynccontextmanager
async def mcp_server_session(
    command: str,
    args: list[str],
    env: dict[str, str] | None = None,
) -> AsyncGenerator[ClientSession, None]:
    """Context manager for managing an MCP server stdio session lifecycle."""
    exit_stack, session = await connect_mcp_server(command, args, env)
    try:
        yield session
    finally:
        await exit_stack.aclose()
