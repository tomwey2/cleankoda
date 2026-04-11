"""
Database repository functions for managing issues and their corresponding branches.
"""

from typing import Any
import logging
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.extensions import db
from app.core.localdb.models import AgentStatesDb

logger = logging.getLogger(__name__)


def read_db_agent_state(id: int | None = None, issue_id: str | None = None) -> AgentStatesDb | None:  # pylint: disable=redefined-builtin
    """Load the saved issue from the database."""
    logger.debug("Reading issue from database with id: %s, issue_id: %s", id, issue_id)
    agent_state = None
    if id is not None:
        agent_state = db.session.get(AgentStatesDb, id)

    # Priority 2: search by issue_id
    elif issue_id is not None:
        stmt = select(AgentStatesDb).where(AgentStatesDb.issue_id == issue_id)
        agent_state = db.session.execute(stmt).scalar_one_or_none()

    # Priority 3 (Fallback): get the first issue
    # We sort by ID, so "the first" is uniquely defined.
    else:
        stmt = select(AgentStatesDb).order_by(AgentStatesDb.id.asc()).limit(1)
        agent_state = db.session.execute(stmt).scalar_one_or_none()

    if agent_state is None:
        logger.warning("No issue found in database")
    else:
        logger.debug("Current issue found: %s (%s)", agent_state.issue_id, agent_state.issue_name)
    return agent_state


def create_db_issue(issue_id: str, issue_name: str) -> AgentStatesDb:
    """insert issue into sqlalchemy database"""
    logger.debug("Creating issue in database: %s (%s)", issue_id, issue_name)
    try:
        new_issue = AgentStatesDb(
            issue_id=issue_id,
            issue_name=issue_name,
        )
        db.session.add(new_issue)
        db.session.commit()
        return new_issue

    except IntegrityError as e:
        # Happens if issue_id (unique=True) is already assigned
        db.session.rollback()
        logging.error("Error creating issue: %s", e)
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught
        db.session.rollback()
        logging.error("Error creating issue: %s", e)
        return None


def update_db_agent_state(issue_id: str, **kwargs: Any) -> AgentStatesDb | None:
    """
    Updates any fields of an issue.
    Call e.g.: update_issue(1, issue_name="New", status="Done", priority=5)
    """
    agent_state = read_db_agent_state(issue_id=issue_id)

    if not agent_state:
        return None

    # Iteriere über alle übergebenen Argumente
    for key, value in kwargs.items():
        # Sicherheits-Check: Hat das Model dieses Attribut überhaupt?
        if hasattr(agent_state, key):
            # Verhindern, dass man aus Versehen die ID ändert (optional, aber empfohlen)
            if key == "id":
                continue

            # Setzt den Wert dynamisch: issue.key = value
            setattr(agent_state, key, value)
        else:
            logging.warning(
                "Attribute '%s' does not exist in issue model and will be ignored.", key
            )

    try:
        logger.debug(
            "Updating issue %d (%s) in database with values: %s",
            agent_state.id,
            agent_state.issue_id,
            kwargs,
        )
        db.session.commit()
        return agent_state
    except Exception as e:  # pylint: disable=broad-exception-caught
        db.session.rollback()
        logging.error("Error updating issue: %s", e)
        return None


def delete_db_issue(issue_id: str) -> bool:
    """
    Removes the issue mapping from the database.
    Returns True if a record was deleted, False otherwise.
    """
    issue = read_db_agent_state(issue_id=issue_id)

    if issue:
        logger.debug("Deleting issue from database: %s", issue_id)
        db.session.delete(issue)
        db.session.commit()
        return True

    return False
