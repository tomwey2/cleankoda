from abc import ABC, abstractmethod
from typing import Any

class Tool(ABC):
    """Abstract base class for all agent tools."""

    @property
    @abstractmethod
    def schema(self) -> list[dict[str, Any]] | dict[str, Any]:
        """Returns the LiteLLM / OpenAI tool schema definition."""
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Executes the tool logic with keyword arguments."""
        pass
