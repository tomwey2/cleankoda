"""
Defines the Explainer node for the agent graph.

The Explainer node loads persisted thought/tool-action history from the
SQLAlchemy database for the current issue.
"""

import logging
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
from sqlalchemy import select

from src.agent.services.prompts import load_prompt
from src.agent.state import AgentState
from src.core.extensions import db
from src.core.database.models import AgentActionDb, AgentStatesDb

logger = logging.getLogger(__name__)

MAX_THOUGHT_EVENTS = 40
MAX_TOOL_EVENTS = 60
MAX_THOUGHT_CHARS = 1000
MAX_TOOL_CHARS = 1300
MAX_VALUE_CHARS = 120


def create_explainer_node(llm):
    """
    Factory function that creates the Explainer node.

    Returns:
        A function that represents the explainer node.
    """

    async def explainer_node(state: AgentState) -> dict[str, Any]:
        if state["current_node"] != "explainer":
            logger.info("--- EXPLAINER node ---")

        issue_id = state["issue_id"]
        if not issue_id:
            logger.warning("Explainer skipped: missing issue_id in state")
            return {"current_node": "explainer"}

        thoughts, tool_actions = _read_issue_thoughts_and_tool_actions(issue_id)
        plan = state["plan_content"]
        formatted_thoughts = _format_thoughts_for_prompt(thoughts)
        formatted_tools_used = _format_tools_for_prompt(tool_actions)

        actions = {
            "plan": plan,
            "thoughts": formatted_thoughts,
            "tools_used": formatted_tools_used,
        }
        system_message = load_prompt(
            "system_messages/systemprompt_explainer.md",
            state | actions,
        )
        response: AIMessage = await llm.ainvoke([SystemMessage(content=system_message)])
        pr_description = _coerce_message_content(response.content)
        logger.info(
            "Loaded %d thoughts and %d tool actions for issue %s",
            len(thoughts),
            len(tool_actions),
            issue_id,
        )

        return {
            "current_node": "explainer",
            "messages": [response],
            "system_prompt": system_message,
            "pr_description": pr_description,
        }

    return explainer_node


def _read_issue_thoughts_and_tool_actions(
    issue_id: str,
) -> tuple[list[AgentActionDb], list[AgentActionDb]]:
    """
    Query all thought and tool-action entries for a issue_id.

    In this codebase, thoughts are represented by AgentAction rows where
    tool_name == "thinking". All other rows are treated as tool actions.
    """
    issue_stmt = select(AgentStatesDb).where(AgentStatesDb.issue_id == issue_id)
    db_issue = db.session.execute(issue_stmt).scalar_one_or_none()
    if not db_issue:
        logger.warning("No AgentIssue found for issue_id=%s", issue_id)
        return [], []

    actions_stmt = (
        select(AgentActionDb)
        .where(AgentActionDb.state_id == db_issue.id)
        .order_by(AgentActionDb.id.asc())
    )
    actions = db.session.execute(actions_stmt).scalars().all()

    thoughts = [action for action in actions if action.tool_name == "thinking"]
    tool_actions = [action for action in actions if action.tool_name != "thinking"]
    return thoughts, tool_actions


def _format_thoughts_for_prompt(thoughts: list[AgentActionDb]) -> str:
    """
    Build compact chronological thought history.
    """
    return _format_action_list_for_prompt(
        title="Thought timeline (oldest -> newest):",
        actions=thoughts,
        kind="thought",
        max_events=MAX_THOUGHT_EVENTS,
        max_chars=MAX_THOUGHT_CHARS,
    )


def _format_tools_for_prompt(tool_actions: list[AgentActionDb]) -> str:
    """
    Build compact chronological tool usage history.
    """
    return _format_action_list_for_prompt(
        title="Tool timeline (oldest -> newest):",
        actions=tool_actions,
        kind="tool",
        max_events=MAX_TOOL_EVENTS,
        max_chars=MAX_TOOL_CHARS,
    )


def _format_action_list_for_prompt(
    title: str,
    actions: list[AgentActionDb],
    kind: str,
    max_events: int,
    max_chars: int,
) -> str:
    """
    Build a compact action list for prompt context.
    """
    sorted_actions = sorted(actions, key=lambda action: (_timestamp_key(action), action.id or 0))

    omitted_for_size = 0
    if len(sorted_actions) > max_events:
        omitted_for_size = len(sorted_actions) - max_events
        sorted_actions = sorted_actions[-max_events:]

    lines: list[str] = [title]
    for action in sorted_actions:
        lines.append(_format_event_line(kind, action))

    lines, omitted_for_chars = _enforce_char_budget(lines, max_chars)
    total_omitted = omitted_for_size + omitted_for_chars
    if total_omitted > 0:
        lines.insert(1, f"... {total_omitted} earlier events omitted for brevity.")

    if len(lines) == 1:
        lines.append("No entries recorded.")

    return "\n".join(lines)


def _enforce_char_budget(lines: list[str], max_chars: int) -> tuple[list[str], int]:
    """
    Ensure output fits within max_chars by dropping oldest event lines first.
    """
    if len("\n".join(lines)) <= max_chars:
        return lines, 0

    trimmed = list(lines)
    removed = 0
    # Keep header at index 0 and remove from index 1 (oldest event first).
    while len(trimmed) > 1 and len("\n".join(trimmed)) > max_chars:
        trimmed.pop(1)
        removed += 1

    return trimmed, removed


def _format_event_line(kind: str, action: AgentActionDb) -> str:
    timestamp = _format_timestamp(action.created_at)
    node_name = (action.node_name or "?").strip()
    tool_name = (action.tool_name or "unknown").strip()

    if kind == "thought":
        return f"- {timestamp} | thought | node={node_name}"

    arg_text = ""
    if action.tool_arg0_name and action.tool_arg0_value:
        value = _truncate(str(action.tool_arg0_value), MAX_VALUE_CHARS)
        arg_text = f" {action.tool_arg0_name}={value}"

    return f"- {timestamp} | tool | {node_name}.{tool_name}{arg_text}"


def _format_timestamp(value: datetime | None) -> str:
    if not value:
        return "unknown-time"
    return value.isoformat(timespec="seconds")


def _timestamp_key(action: AgentActionDb) -> datetime:
    return action.created_at or datetime.min


def _truncate(value: str, max_chars: int) -> str:
    clean_value = " ".join(value.split())
    if len(clean_value) <= max_chars:
        return clean_value
    return clean_value[: max_chars - 3] + "..."


def _coerce_message_content(content: Any) -> str:
    """
    Convert LLM response content to plain text.
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part.strip() for part in parts if part and part.strip())
    return str(content).strip()
