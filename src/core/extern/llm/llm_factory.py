"""
Factory module for creating LangChain LLM instances.

This module provides a centralized way to instantiate different chat models
(LLMs) from various providers like OpenAI, Google, Mistral, etc.
It uses EnvironmentSettings for API key retrieval.

The main function is `get_llm`, which takes a configuration and returns
an appropriate `BaseChatModel` instance.
"""

import logging
from typing import Callable, Dict

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mistralai import ChatMistralAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from src.core.database.models import AgentSettingsDb, UserCredentialDb
from src.core.services.credentials_service import get_credential_by_id

logger = logging.getLogger(__name__)


def _create_openai_llm(
    model: str, temperature: float, credential: UserCredentialDb
) -> BaseChatModel:
    api_key = credential.api_key
    return ChatOpenAI(model=model, temperature=temperature, api_key=SecretStr(api_key))


def _create_mistral_llm(
    model: str, temperature: float, credential: UserCredentialDb
) -> BaseChatModel:
    api_key = credential.api_key
    return ChatMistralAI(model_name=model, temperature=temperature, api_key=SecretStr(api_key))


def _create_google_llm(
    model: str, temperature: float, credential: UserCredentialDb
) -> BaseChatModel:
    api_key = credential.api_key
    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        google_api_key=api_key,
        convert_system_message_to_human=True,
    )


def _create_openrouter_llm(
    model: str, temperature: float, credential: UserCredentialDb
) -> BaseChatModel:
    api_key = credential.api_key
    base_url = credential.base_url
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        base_url=base_url,
        api_key=SecretStr(api_key),
    )


def _create_anthropic_llm(
    model: str, temperature: float, credential: UserCredentialDb
) -> BaseChatModel:
    api_key = credential.api_key
    return ChatAnthropic(
        model=model,
        temperature=temperature,
        api_key=api_key,
    )


def _create_ollama_llm(
    model: str, temperature: float, credential: UserCredentialDb
) -> BaseChatModel:
    base_url = credential.base_url
    api_key = credential.api_key
    logger.info("Using Ollama base URL: %s", base_url)
    return ChatOllama(
        model=model,
        temperature=temperature,
        base_url=base_url,
        api_key=api_key,
    )


LLM_PROVIDERS: Dict[str, Callable[[str, float], BaseChatModel]] = {
    "OPENAI": _create_openai_llm,
    "MISTRAL": _create_mistral_llm,
    "GOOGLE": _create_google_llm,
    "GEMINI": _create_google_llm,
    "OPENROUTER": _create_openrouter_llm,
    "OLLAMA": _create_ollama_llm,
    "ANTHROPIC": _create_anthropic_llm,
}


def get_llm(agent_settings: AgentSettingsDb, large: bool = True) -> BaseChatModel:
    """
    Factory function to get an LLM instance based on the provider.

    :param agent_settings: Agent settings providing llm_* fields.
    :param large: If True, use llm_model_large; otherwise use llm_model_small.
    :return: An instance of a class that inherits from BaseChatModel.
    :raises ValueError: If provider is not specified, model is not specified,
                       or provider is unknown.
    """
    credential = get_credential_by_id(agent_settings.llm_credential_id)
    if not credential.credential_type:
        raise ValueError("llm_provider not specified")

    model = agent_settings.llm_model_large if large else agent_settings.llm_model_small
    if not model:
        raise ValueError("llm_model not specified")

    temperature_value = agent_settings.llm_temperature
    temperature = float(temperature_value or 0.0)

    provider_factory = LLM_PROVIDERS.get(credential.credential_type)
    if not provider_factory:
        raise ValueError(f"Unknown LLM provider: {credential.credential_type}")

    logger.debug(
        "Creating LLM: provider=%s, model=%s, temperature=%s",
        credential.credential_type,
        model,
        temperature,
    )
    return provider_factory(model, temperature, credential)
