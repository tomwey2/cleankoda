"""Service function for the plan."""

import logging
import os

from app.agent.utils import get_instance_dir

logger = logging.getLogger(__name__)


def delete_plan():
    """Remove the plan.md content from the instance dir."""
    instance_dir = get_instance_dir()
    plan_path = os.path.join(instance_dir, "plan.md")

    if os.path.exists(plan_path):
        os.remove(plan_path)  # Alternativ: os.unlink(datei_pfad)
        print("plan.md is removed")


def exist_plan() -> bool:
    """Check if the plan.md exists in the instance dir.

    Returns:
        True if plan.md exists, False otherwise.
    """
    instance_dir = get_instance_dir()
    plan_path = os.path.join(instance_dir, "plan.md")
    return os.path.exists(plan_path)


def get_plan() -> str:
    """Read and return the plan.md content from the instance dir.

    Returns:
        Content of plan.md or a default message if not found.
    """
    instance_dir = get_instance_dir()
    plan_path = os.path.join(instance_dir, "plan.md")

    if not os.path.exists(plan_path):
        return "No plan.md found in instance dir."

    try:
        with open(plan_path, "r", encoding="utf-8") as f:
            return f.read()
    except (IOError, OSError) as e:
        logger.error("Error reading plan.md: %s", e)
        return f"Error reading plan.md: {e}"
