from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncGenerator

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def connect_mcp_server(
    command: str,
    args: list[str],
    env: dict[str, str] | None = None,
) -> tuple[AsyncExitStack, ClientSession]:
    """Connects to an MCP server via stdio transport and returns the exit stack and session."""
    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=env,
    )
    exit_stack = AsyncExitStack()
    try:
        read_stream, write_stream = await exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        session = await exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()
        return exit_stack, session
    except Exception:
        await exit_stack.aclose()
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
