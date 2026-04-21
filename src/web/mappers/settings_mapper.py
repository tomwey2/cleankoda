"""Mappers for converting between web schemas and database models.

This module provides bidirectional mapping between:
- Web layer schemas (Pydantic models for form data)
- Database layer models (SQLAlchemy ORM models)
"""

from typing import Any, Dict

from flask import request

from src.core.localdb.models import AgentSettingsDb
from src.web.schemas.settings_schema import (
    LLMConfigSchema,
    SettingsFormSchema,
    ItsConfigSchema,
)
from src.core.types import IssueTrackingSystemType, SkillLevelType, GenderType


def form_to_schema() -> SettingsFormSchema:
    """Parse Flask form data into a validated SettingsFormSchema.

    Returns:
        SettingsFormSchema with validated form data.
    """
    its_type = request.form.get("its_type", IssueTrackingSystemType.TRELLO)

    # Always parse all provider configs from form
    its_config = ItsConfigSchema(
        its_api_key=request.form.get("its_api_key"),
        its_api_token=request.form.get("its_api_token"),
        its_base_url=request.form.get("its_base_url", "https://api.trello.com/1"),
        its_container_id=request.form.get("its_container_id"),
        its_state_backlog=request.form.get("its_state_backlog"),
        its_state_todo=request.form.get("its_state_todo"),
        its_state_in_progress=request.form.get("its_state_in_progress"),
        its_state_in_review=request.form.get("its_state_in_review"),
        its_state_done=request.form.get("its_state_done"),
    )

    llm_config = LLMConfigSchema(
        llm_provider=request.form.get("llm_provider", ""),
        llm_model_large=request.form.get("llm_model_large"),
        llm_model_small=request.form.get("llm_model_small"),
        llm_temperature=request.form.get("llm_temperature"),
    )

    return SettingsFormSchema(
        its_type=its_type,
        agent_skill_level=request.form.get("agent_skill_level"),
        agent_gender=request.form.get("agent_gender"),
        polling_interval_seconds=int(request.form.get("polling_interval_seconds", "60")),
        is_active="is_active" in request.form,
        repo_type=request.form.get("repo_type"),
        repo_url=request.form.get("repo_url"),
        its_config=its_config,
        llm_config=llm_config,
    )


def schema_to_model(schema: SettingsFormSchema, settings: AgentSettingsDb) -> AgentSettingsDb:
    """Apply schema values to an AgentSettings model.

    Args:
        schema: Validated settings form schema.
        settings: Existing AgentSettings to update (or new instance).

    Returns:
        Updated AgentSettings model (not yet committed).
    """
    settings.its_type = schema.its_type
    settings.agent_skill_level = SkillLevelType.from_string(schema.agent_skill_level)
    settings.agent_gender = GenderType.from_string(schema.agent_gender)
    settings.polling_interval_seconds = schema.polling_interval_seconds
    settings.is_active = schema.is_active
    settings.repo_type = schema.repo_type
    settings.repo_url = schema.repo_url

    _apply_llm_config(schema.llm_config, settings)
    _apply_its_config(schema.its_config, settings)

    return settings


def _apply_llm_config(llm_schema: LLMConfigSchema, settings: AgentSettingsDb) -> None:
    """Apply LLM configuration from schema to model."""
    settings.llm_provider = llm_schema.llm_provider
    settings.llm_model_large = llm_schema.llm_model_large
    settings.llm_model_small = llm_schema.llm_model_small
    settings.llm_temperature = llm_schema.llm_temperature


def _apply_its_config(its_schema: ItsConfigSchema, settings: AgentSettingsDb) -> None:
    """Apply Trello configuration from schema to model."""

    settings.its_container_id = its_schema.its_container_id
    settings.its_api_key = its_schema.its_api_key
    settings.its_token = its_schema.its_api_token
    settings.its_base_url = its_schema.its_base_url
    settings.its_state_backlog = its_schema.its_state_backlog
    settings.its_state_todo = its_schema.its_state_todo
    settings.its_state_in_progress = its_schema.its_state_in_progress
    settings.its_state_in_review = its_schema.its_state_in_review
    settings.its_state_done = its_schema.its_state_done


def model_to_form_data(settings: AgentSettingsDb) -> Dict[str, Any]:
    """Convert AgentSettings model to form data dictionary for template rendering.

    Args:
        settings: AgentSettings model to convert.

    Returns:
        Dictionary suitable for populating the settings form template.
    """
    form_data: Dict[str, Any] = {
        "agent_skill_level": settings.agent_skill_level,
        "agent_gender": settings.agent_gender,
        "its_api_key": settings.its_api_key,
        "its_api_token": settings.its_token,
        "its_container_id": settings.its_container_id,
        "its_base_url": settings.its_base_url,
        "its_state_backlog": settings.its_state_backlog,
        "its_state_todo": settings.its_state_todo,
        "its_state_in_progress": settings.its_state_in_progress,
        "its_state_in_review": settings.its_state_in_review,
        "its_state_done": settings.its_state_done,
        "repo_type": settings.repo_type,
        "repo_url": settings.repo_url,
        "llm_provider": settings.llm_provider,
        "llm_model_large": settings.llm_model_large,
        "llm_model_small": settings.llm_model_small,
        "llm_temperature": settings.llm_temperature,
    }

    return form_data
