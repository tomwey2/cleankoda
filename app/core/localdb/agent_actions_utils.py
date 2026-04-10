import logging
from sqlalchemy.exc import IntegrityError

from app.core.extensions import db
from app.core.localdb.models import AgentActionDb, AgentStatesDb
from sqlalchemy import select

logger = logging.getLogger(__name__)


def read_db_agent_actions(agent_issue: AgentStatesDb) -> list[AgentActionDb]:
    """Get the actions from the database for a given issue."""
    stmt = (
        select(AgentActionDb)
        .where(AgentActionDb.issue_id == agent_issue.id)
        .order_by(AgentActionDb.id.asc())
    )
    return db.session.execute(stmt).scalars().all()


def create_db_agent_action(state: dict):
    """insert agent state into sqlalchemy database"""

    tool_calls: list[dict] = state.get("tool_calls", [])
    current_node: str | None = state.get("current_node", None)
    agent_issue: AgentStatesDb = state.get("agent_issue", None)

    if current_node is None or not tool_calls:
        return None

    try:
        for tool_call in tool_calls:
            name = tool_call.get("name", "unknown")
            logger.debug(
                "Creating agent state in database for current_node: %s tool: %s",
                current_node,
                name,
            )
            args = tool_call.get("args", {}) or {}
            arg0_name = ""
            arg0_value = ""
            if args and name in ["read_file", "write_to_file", "run_command"]:
                arg0_name, arg0_value = next(iter(args.items()))

            last_agent_action = get_last_agent_action()
            if (
                last_agent_action
                and last_agent_action.current_node == current_node
                and last_agent_action.tool_name == name
                and last_agent_action.tool_arg0_name == arg0_name
                and last_agent_action.tool_arg0_value == arg0_value
            ):
                return
            new_agent_action = AgentActionDb(
                state_id=agent_issue.id,
                current_node=current_node,
                tool_name=name,
                tool_arg0_name=arg0_name,
                tool_arg0_value=arg0_value,
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


def get_last_agent_action() -> AgentActionDb | None:
    """Get the last action from the database."""
    stmt = select(AgentActionDb).order_by(AgentActionDb.id.desc())
    return db.session.execute(stmt).scalar()
