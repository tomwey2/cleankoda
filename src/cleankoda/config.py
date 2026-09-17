from cleankoda import sandbox
import os
from pathlib import Path
from pydantic import BaseModel, Field

from cleankoda.llm.credentials import CredentialsStore

CONFIG_DIR = Path.home() / ".config" / "cleankoda"
CONFIG_FILE = CONFIG_DIR / "config.json"

def get_config_file() -> Path:
  if custom_dir := os.getenv("CLEANKODA_CONFIG_DIR"):
    return Path(custom_dir) / "config.json"
  return CONFIG_FILE


class AppConfig(BaseModel):
    workspace: Path = Path.cwd()
    provider: str = "mistral"
    model: str = "mistral-small-latest"
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    sandbox: str = ""

    # Issue tracking system: e.g., "TRELLO", "JIRA", "GITHUB ISSUES"
    its_type: str = ""
    its_base_url: str = ""
    its_container_id: str = ""
    its_parent_id: str = ""
    its_state_backlog: str = "backlog"
    its_state_todo: str = "todo"
    its_state_in_progress: str = "in progress"
    its_state_in_review: str = "in review"
    its_state_done: str = "done"

    @property
    def litellm_model_identifier(self) -> str:
        """Mappt Provider und Modell auf LiteLLM-kompatible Präfixe."""
        from cleankoda.llm.config import get_provider_config

        provider_lower = self.provider.lower()
        model_str = self.model

        p_config = get_provider_config(provider_lower)
        if p_config and p_config.is_custom:
            if model_str.startswith("openai/"):
                return model_str
            return f"openai/{model_str}"

        if "/" in model_str:
            return model_str

        if provider_lower == "google":
            if model_str.startswith("gemini/") or model_str.startswith("google/"):
                return model_str
            return f"gemini/{model_str}"

        if provider_lower in ["ollama", "openrouter", "anthropic", "openai", "mistral"]:
            return f"{provider_lower}/{model_str}"

        return f"openai/{model_str}"

    @classmethod
    def load(cls) -> "AppConfig":
        """Loads the configuration from the JSON file or creates a new one with defaults."""
        target_path = get_config_file()
        if target_path.is_file():
            content = target_path.read_text(encoding="utf-8")
            return cls.model_validate_json(content)

        # If the file does not yet exist: create and save the default object.
        instance = cls()
        instance.save()
        return instance

    def save(self) -> None:
        """Saves the current state back to the JSON file in a formatted manner."""
        target_path = get_config_file()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        json_str = self.model_dump_json(indent=2)
        target_path.write_text(json_str, encoding="utf-8")
        try:
            os.chmod(target_path, 0o600)
        except OSError:
            pass

    def get_active_api_key(self, credentials_file: Path | None = None) -> str | None:
        """Holt den aktiven API-Key über den CredentialsStore."""
        store = CredentialsStore.load(file_path=credentials_file)
        return store.get_key(self.provider)

    def get_credential_by_key(self, key: str, credentials_file: Path | None = None) -> str | None:
        """Holt den aktiven API-Key über den CredentialsStore."""
        store = CredentialsStore.load(file_path=credentials_file)
        return store.get_key(key)


config = AppConfig.load()
