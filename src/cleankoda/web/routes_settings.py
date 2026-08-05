"""Defines the routes for the web application's settings pages."""

import logging

from flask import (
    Blueprint,
    flash,
    render_template,
    request,
)

from cleankoda.core.services import agent_settings_service, users_service
from cleankoda.web.services import settings_service

logger = logging.getLogger(__name__)

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings", methods=["GET", "POST"])
def settings():
    """Handles the settings page."""
    user_id = users_service.get_current_user_id()
    agent_settings = agent_settings_service.get_or_create_agent_settings(user_id)

    if request.method == "POST":
        try:
            settings_service.save_settings(agent_settings)
            flash("Settings saved successfully!", "success")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Failed to save settings")
            flash(f"Error saving settings: {str(e)}", "danger")
        # Re-fetch settings to show updated values
        agent_settings = agent_settings_service.get_or_create_agent_settings(user_id)

    context = settings_service.get_template_context(agent_settings)
    return render_template("settings.html", **context)
