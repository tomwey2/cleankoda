"""Defines the routes for the web application's credentials pages."""

import logging

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from src.core.services import credentials_service, users_service

logger = logging.getLogger(__name__)

credentials_bp = Blueprint("credentials", __name__)


@credentials_bp.route("/credentials", methods=["GET"])
def credentials_overview():
    """Handles the credentials overview page."""
    user_id = users_service.get_current_user_id()
    credentials = credentials_service.get_credentials_for_user(user_id)
    return render_template("credentials_overview.html", credentials=credentials)


@credentials_bp.route("/credentials/new", methods=["GET"])
def credentials_new_selection():
    """Handles the credential type selection page."""
    # List of available credential types
    credential_types = [
        {
            "id": "GITHUB",
            "name": "GitHub PAT",
            "icon": "bi-github",
            "description": "Personal Access Token for GitHub",
        },
        {
            "id": "JIRA",
            "name": "Jira Basic Auth",
            "icon": "bi-bezier",
            "description": "Email and API Token for Jira",
        },
        {
            "id": "TRELLO",
            "name": "Trello Key",
            "icon": "bi-trello",
            "description": "API Key and Token for Trello",
        },
        {
            "id": "MISTRAL",
            "name": "Mistral API Key",
            "icon": "bi-cpu",
            "description": "API Key for Mistral",
        },
        {
            "id": "GEMINI",
            "name": "Gemini API Key",
            "icon": "bi-cpu",
            "description": "API Key for Gemini",
        },
        {
            "id": "OPENAI",
            "name": "OpenAI API Key",
            "icon": "bi-cpu",
            "description": "API Key for OpenAI",
        },
        {
            "id": "ANTHROPIC",
            "name": "Anthropic API Key",
            "icon": "bi-cpu",
            "description": "API Key for Anthropic",
        },
        {
            "id": "OLLAMA",
            "name": "Local LLM with Ollama",
            "icon": "bi-cpu",
            "description": "Ollama API Key",
        },
        {
            "id": "OPENROUTER",
            "name": "OpenRouter API Key",
            "icon": "bi-cpu",
            "description": "OpenRouter API Key",
        },
        {
            "id": "BASIC_AUTH",
            "name": "Basic Auth",
            "icon": "bi-person",
            "description": "Basic Auth for username and password",
        },
    ]
    return render_template("credentials_new.html", types=credential_types)


@credentials_bp.route("/credentials/new/<credential_type>", methods=["GET", "POST"])
def credentials_new_form(credential_type: str):
    """Handles the credential creation form for a specific type."""
    user_id = users_service.get_current_user_id()

    if request.method == "POST":
        try:
            data = request.form.to_dict()
            data["credential_type"] = credential_type
            credentials_service.save_credential(user_id, data)
            flash("Credential saved successfully!", "success")
            return redirect(url_for("credentials.credentials_overview"))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Failed to save credential")
            flash(f"Failed to save credential: {str(e)}", "danger")

    return render_template("credentials_form.html", credential_type=credential_type)


@credentials_bp.route("/credentials/<int:credential_id>/edit", methods=["GET", "POST"])
def credentials_edit(credential_id: int):
    """Handles editing an existing credential."""
    user_id = users_service.get_current_user_id()
    credential = credentials_service.get_credential_by_id(credential_id)
    if not credential:
        flash("Credential not found.", "danger")
        return redirect(url_for("credentials.credentials_overview"))

    if request.method == "POST":
        try:
            data = request.form.to_dict()
            data["id"] = credential_id
            credentials_service.save_credential(user_id, data)
            flash("Credential updated successfully!", "success")
            return redirect(url_for("credentials.credentials_overview"))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Failed to update credential")
            flash(f"Failed to update credential: {str(e)}", "danger")

    return render_template(
        "credentials_form.html", credential_type=credential.credential_type, credential=credential
    )


@credentials_bp.route("/credentials/<int:credential_id>/delete", methods=["POST"])
def credentials_delete(credential_id: int):
    """Handles deleting a credential."""
    user_id = users_service.get_current_user_id()
    success = credentials_service.delete_credential(user_id, credential_id)
    if success:
        flash("Credential deleted successfully!", "success")
    else:
        flash("Failed to delete credential.", "danger")
    return redirect(url_for("credentials.credentials_overview"))
