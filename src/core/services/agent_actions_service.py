import logging
from sqlalchemy.exc import IntegrityError

from src.core.extensions import db
from src.core.database.models import AgentActionDb, AgentStatesDb
from sqlalchemy import select
from src.core.services.agent_states_service import get_agent_state_by_id

logger = logging.getLogger(__name__)


def get_agent_actions_by_issue_id(user_id: str, issue_id: str) -> list[AgentActionDb]:
    """Get the actions from the database for a given issue."""
    agent_state: AgentStatesDb | None = get_agent_state_by_id(user_id=user_id, issue_id=issue_id)
    if not agent_state:
        return []

    stmt = (
        select(AgentActionDb)
        .filter_by(user_id=user_id)
        .where(AgentActionDb.state_id == agent_state.id)
        .order_by(AgentActionDb.id.asc())
    )
    return db.session.execute(stmt).scalars().all()


def create_agent_action(user_id: str, agent_state_id: int, tool_calls: list[dict], node_name: str):
    """insert agent state into sqlalchemy database"""
    if node_name is None or not tool_calls:
        return

    try:
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "unknown")
            logger.debug(
                "Creating agent state in database for node: %s tool: %s",
                node_name,
                tool_name,
            )
            args = tool_call.get("args", {}) or {}
            tool_arg0_name = ""
            tool_arg0_value = ""
            if args and tool_name in ["read", "write", "bash"]:
                tool_arg0_name, tool_arg0_value = next(iter(args.items()))

            last_agent_action = get_last_agent_action(user_id)
            if (
                last_agent_action
                and last_agent_action.node_name == node_name
                and last_agent_action.tool_name == tool_name
                and last_agent_action.tool_arg0_name == tool_arg0_name
                and last_agent_action.tool_arg0_value == tool_arg0_value
            ):
                return
            new_agent_action = AgentActionDb(
                user_id=user_id,
                state_id=agent_state_id,
                node_name=node_name,
                tool_name=tool_name,
                tool_arg0_name=tool_arg0_name,
                tool_arg0_value=tool_arg0_value,
            )
            db.session.add(new_agent_action)
            db.session.commit()
        return

    except IntegrityError as e:
        # Happens if issue_id (unique=True) is already assigned
        db.session.rollback()
        logging.error("Error creating agent action: %s", e)
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught
        db.session.rollback()
        logging.error("Error creating agent action: %s", e)
        return None


def get_last_agent_action(user_id: str) -> AgentActionDb | None:
    """Get the last action from the database."""
    stmt = select(AgentActionDb).filter_by(user_id=user_id).order_by(AgentActionDb.id.desc())
    return db.session.execute(stmt).scalar()
