"""Defines the routes for the web application's dashboard pages."""

import logging

from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
)

from src.web.services import dashboard_service
from src.web.services.dashboard_service import PlanReviewError, process_plan_review
from src.core.types import PlanState
from src.core.services import users_service

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard", methods=["GET"])
async def dashboard():
    """Handles the main dashboard page."""
    user_id = users_service.get_current_user_id()
    context = await dashboard_service.get_template_context(user_id)
    return render_template("dashboard.html", **context)


@dashboard_bp.route("/api/issue/review_plan", methods=["POST"])
async def review_plan():
    """Updates the plan state of the current issue."""
    user_id = users_service.get_current_user_id()
    data = request.json or {}
    new_state = PlanState.from_string(data.get("plan_state"))
    rejection_reason = data.get("rejection_reason")

    try:
        result = await process_plan_review(user_id, new_state, rejection_reason)
        return jsonify(result)
    except PlanReviewError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error while updating plan state")
        return jsonify({"error": "Failed to update issue"}), 500


@dashboard_bp.route("/api/trigger_agent", methods=["POST"])
async def trigger_agent():
    """Triggers the agent to process the current issue."""
    user_id = users_service.get_current_user_id()
    # Supabase handling
    issue = await dashboard_service.get_next_open_issue(user_id)
    if issue:
        await dashboard_service.trigger_agent_job(user_id, issue)
    return jsonify({"status": "Sync triggered"}), 200
