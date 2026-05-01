"""The routes for the web application.

This module uses a Flask Blueprint to organize the routes as thin controllers.
Route handlers delegate business logic to the service layer and focus only on
HTTP request/response handling.
"""

import logging

from flask import (
    Blueprint,
    render_template,
)

logger = logging.getLogger(__name__)

web_bp = Blueprint("web", __name__, template_folder="templates", static_folder="static")


@web_bp.route("/", methods=["GET"])
def landing():
    """Handles the landing page."""
    return render_template("index.html")
