import logging
import os
import re
import shutil
from typing import Any, Optional

from git import Repo
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from agent.state import AgentState

logger = logging.getLogger(__name__)


def safe_truncate(value: Any, length: int = 100) -> str:
    """
    Converts any value to string, truncates it to the desired length,
    and replaces newlines for cleaner log output.
    """
    string_value = str(value)
    if len(string_value) > length:
        return string_value[:length] + "..."
    return string_value.replace("\n", "\\n")


def log_agent_response(
    logger_obj: logging.Logger,
    agent_name: str,
    response: AIMessage,
    attempt: Optional[int] = None,
    content_limit: int = 150,
    arg_limit: int = 250,
) -> None:
    """
    Logs LLM responses consistently across nodes, including tool calls and content.
    """
    header = f"\n=== {agent_name.upper()} RESPONSE"
    if attempt is not None:
        header += f" (Attempt {attempt})"
    header += " ==="
    logger_obj.info(header)

    tool_calls = getattr(response, "tool_calls", []) or []
    if tool_calls:
        for tool_call in tool_calls:
            name = tool_call.get("name", "unknown")
            logger_obj.info("Tool Call: %s", name)
            args = tool_call.get("args", {}) or {}
            for key, value in args.items():
                logger_obj.info(
                    " └─ %s: %s", key, safe_truncate(value, length=arg_limit)
                )

    if getattr(response, "content", None):
        logger_obj.info("Content: %s", safe_truncate(response.content, content_limit))


def log_agent_state(
    logger_obj: logging.Logger,
    state: AgentState,
    content_limit: int = 100,
    arg_limit: int = 250,
) -> None:
    """
    Logs a snapshot of the AgentState, including a detailed message dump.
    """
    if state is None:
        logger_obj.info("AgentState: <empty>")
        return

    logger_obj.info("\n=== AGENT STATE SNAPSHOT ===")
    logger_obj.info("next_step        : %s", state.get("next_step"))
    logger_obj.info("agent_stack      : %s", state.get("agent_stack"))
    logger_obj.info("retry_count      : %s", state.get("retry_count"))
    logger_obj.info("test_result      : %s", state.get("test_result"))
    logger_obj.info("error_log        : %s", state.get("error_log"))
    logger_obj.info("trello_card_id   : %s", state.get("trello_card_id"))
    logger_obj.info("trello_list_id   : %s", state.get("trello_list_id"))
    logger_obj.info("trello_in_progress: %s", state.get("trello_in_progress"))

    messages = state.get("messages") or []
    logger_obj.info("\n--- Messages (%d) ---", len(messages))
    for idx, message in enumerate(messages, start=1):
        msg_type = getattr(message, "type", message.__class__.__name__)
        logger_obj.info("[%02d] %s", idx, msg_type.upper())

        content = getattr(message, "content", None)
        if content is not None:
            logger_obj.info("     content       : %s", safe_truncate(content, content_limit))

        name = getattr(message, "name", None)
        if name:
            logger_obj.info("     name          : %s", name)

        tool_call_id = getattr(message, "tool_call_id", None)
        if tool_call_id:
            logger_obj.info("     tool_call_id  : %s", tool_call_id)

        additional_kwargs = getattr(message, "additional_kwargs", None) or {}
        if additional_kwargs:
            logger_obj.info("     additional_kwargs:")
            for key, value in additional_kwargs.items():
                logger_obj.info("         %s: %s", key, safe_truncate(value, arg_limit))

        tool_calls = getattr(message, "tool_calls", None) or []
        if tool_calls:
            logger_obj.info("     tool_calls:")
            for tool_idx, tool_call in enumerate(tool_calls, start=1):
                name = tool_call.get("name", "unknown")
                logger_obj.info("         (%d) %s", tool_idx, name)
                args = tool_call.get("args", {}) or {}
                for key, value in args.items():
                    logger_obj.info(
                        "             %s: %s", key, safe_truncate(value, arg_limit)
                    )

        if isinstance(message, ToolMessage):
            tool_payload = getattr(message, "tool_call_results", None)
            if tool_payload is not None:
                logger_obj.info(
                    "     tool_call_results: %s",
                    safe_truncate(tool_payload, arg_limit),
                )

    logger_obj.info("=== END OF STATE SNAPSHOT ===")

# Hilfsfunktion, um Redundanz zu vermeiden
def get_workspace():
    # Holt den Pfad aus der Env-Var, die wir im Docker-Compose gesetzt haben
    return os.environ.get("WORKSPACE", "/coding-agent-workspace")


def get_workbench():
    # Holt den Pfad aus der Env-Var, die wir im Docker-Compose gesetzt haben
    return os.environ.get("WORKBENCH", "")


def load_system_prompt(stack: str, role: str) -> str:
    """
    Lädt den System-Prompt basierend auf Stack und Rolle.
    z.B. stack="backend", role="coder" -> liest workbench/backend/systemprompt_coder.md
    """

    file_path = os.path.join("workbench", stack, f"systemprompt_{role}.md")

    logger.info(f"Loading system prompt: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # Fallback, falls Datei fehlt (wichtig für Robustheit!)
        logger.warning(f"WARNUNG: System Prompt not found: {file_path}")
        return "You are a helpful coding assistent."


def _estimate_tokens(messages: list[BaseMessage]) -> int:
    """Rough estimate of token count for messages (avg ~4 chars per token)."""
    total_chars = 0
    for msg in messages:
        if hasattr(msg, 'content') and msg.content:
            total_chars += len(str(msg.content))
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            total_chars += len(str(msg.tool_calls))
    return total_chars // 4


def _find_first_human_message(messages: list[BaseMessage]) -> int:
    """Find index of first HumanMessage (original task)."""
    # Scan through messages to locate the first HumanMessage
    # This represents the original user task/request
    for idx, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            return idx
    return None


def _find_safe_start_boundary(messages: list[BaseMessage], recent_start_idx: int) -> int:
    """
    Find a safe starting point by scanning forward from the cutoff.
    Safe boundaries are: HumanMessage or AIMessage
    """
    adjusted_start_idx = recent_start_idx
    
    # Scan forward from the naive cutoff point to find a valid conversation boundary
    for idx in range(recent_start_idx, len(messages)):
        msg = messages[idx]
        
        # HumanMessages are always safe starting points (no dependent tool responses)
        if isinstance(msg, HumanMessage) or isinstance(msg, AIMessage):
            adjusted_start_idx = idx
            break
    
    return adjusted_start_idx


def _trim_trailing_invalid_ai_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """
    Remove trailing AIMessages without tool_calls.
    Mistral API requires last message to be User, Tool, or Assistant with tool_calls.
    """
    # Remove any trailing AI messages that don't have tool calls
    # Mistral API enforces: last message must be user/tool/assistant-with-tool-calls
    while messages and isinstance(messages[-1], AIMessage):
        ai_msg = messages[-1]
        # If this AI message has tool calls, it's valid as the last message
        if getattr(ai_msg, 'tool_calls', None):
            break
        # Otherwise, remove it and check the previous message
        messages = messages[:-1]
    return messages


def _log_token_savings(original_count: int, original_tokens: int, 
                       filtered_count: int, filtered_tokens: int) -> None:
    """Log token savings statistics."""
    # Calculate absolute and percentage token savings
    saved_tokens = original_tokens - filtered_tokens
    saved_percentage = (saved_tokens / original_tokens * 100) if original_tokens > 0 else 0
    
    # Log the filtering results for monitoring token optimization
    logger.info(
        f"Message filter: {original_count} → {filtered_count} messages "
        f"(~{original_tokens} → ~{filtered_tokens} tokens, "
        f"saved ~{saved_tokens} tokens / {saved_percentage:.1f}%)"
    )


def filter_messages_for_llm(messages: list[BaseMessage], max_messages: int = 10) -> list[BaseMessage]:
    """
    Filters messages to keep only the most recent and relevant ones for LLM context.
    This reduces token usage by limiting the message history.
    
    Strategy:
    - Always keep the first HumanMessage (original task)
    - Keep the most recent complete conversation turns
    - Never break AI→Tool message pairs to maintain valid message order
    - Prevent orphaned ToolMessages that would violate API constraints
    
    :param messages: List of messages from state
    :param max_messages: Maximum number of messages to keep (excluding first task message)
    :return: Filtered list of messages
    """
    # Early exit for empty list
    if not messages:
        return []
    
    # Track original metrics for logging
    original_count = len(messages)
    original_tokens = _estimate_tokens(messages)
    
    # Skip filtering if message count is already within limits
    if len(messages) <= max_messages + 1:
        logger.debug(f"Message filter: {original_count} messages, ~{original_tokens} tokens (no filtering needed)")
        return messages
    
    # Step 1: Find the original user task (first HumanMessage)
    first_human_idx = _find_first_human_message(messages)
    
    # Step 2: Calculate naive cutoff and find safe conversation boundary
    recent_start_idx = max(0, len(messages) - max_messages)
    adjusted_start_idx = _find_safe_start_boundary(messages, recent_start_idx)
    
    # Step 3: Extract recent messages and trim invalid trailing AI messages
    recent_messages = messages[adjusted_start_idx:]
    recent_messages = _trim_trailing_invalid_ai_messages(recent_messages)
    
    # Step 4: Fallback if everything was filtered out
    if not recent_messages and messages:
        # Try to return at least the last HumanMessage
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return [msg]
        # Ultimate fallback: return last message
        return [messages[-1]] if messages else []
    
    # Step 5: Prepend original task if it was filtered out
    if first_human_idx is not None and first_human_idx < adjusted_start_idx:
        first_task = [messages[first_human_idx]]
        filtered_messages = first_task + recent_messages
    else:
        filtered_messages = recent_messages
    
    # Step 6: Log token savings
    filtered_count = len(filtered_messages)
    filtered_tokens = _estimate_tokens(filtered_messages)
    _log_token_savings(original_count, original_tokens, filtered_count, filtered_tokens)
    
    return filtered_messages


def sanitize_response(response: AIMessage) -> AIMessage:
    """
    Entfernt halluzinierte Tool-Calls (z.B. wenn der Name ein ganzer Satz ist).
    Verhindert API Fehler 3280 (Invalid function name).
    """
    # Wenn keine Tool Calls da sind oder es keine AI Message ist, einfach zurückgeben
    if not isinstance(response, AIMessage) or not response.tool_calls:
        return response

    valid_tools = []
    # Erlaubte Zeichen für Funktionsnamen: a-z, A-Z, 0-9, _, -
    name_pattern = re.compile(r"^[a-zA-Z0-9_-]+$")

    for tc in response.tool_calls:
        name = tc.get("name", "")
        # Check: Ist der Name im gültigen Format und nicht zu lang?
        if name_pattern.match(name) and len(name) < 64:
            valid_tools.append(tc)
        else:
            logger.warning(f"SANITIZER: Removed invalid tool call with name: '{name}'")

    # Das manipulierte Objekt zurückgeben
    response.tool_calls = valid_tools
    return response


def save_graph_as_png(graph):
    # 1. Die Bilddaten in einer Variable speichern (es sind Bytes)
    png_bytes = graph.get_graph().draw_mermaid_png()

    # 2. Datei im 'write binary' Modus ("wb") öffnen und speichern
    with open("workflow_graph.png", "wb") as f:
        f.write(png_bytes)

    print("Graph wurde als 'workflow_graph.png' gespeichert.")


def save_graph_as_mermaid(graph):
    # 1. Die Bilddaten in einer Variable speichern (es sind Bytes)
    mermaid_code = graph.get_graph().draw_mermaid()

    # 2. Datei im 'write binary' Modus ("wb") öffnen und speichern
    with open("workflow_graph.mmd", "w") as f:
        f.write(mermaid_code)

    print("Graph wurde als 'workflow_graph.mmd' gespeichert.")


def ensure_repository_exists(repo_url, work_dir):
    """
    Stellt sicher, dass work_dir ein valides Git-Repo ist.
    """
    # 1. Inhalt löschen, aber NICHT den Ordner selbst (wegen Mount)
    for filename in os.listdir(work_dir):
        file_path = os.path.join(work_dir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")

    # 2. In das nun leere Verzeichnis klonen
    # Der Punkt '.' ist wichtig, damit git nicht einen Unterordner erstellt
    logger.info(f"Cloning repository {repo_url} into {work_dir}")
    Repo.clone_from(repo_url, work_dir)
