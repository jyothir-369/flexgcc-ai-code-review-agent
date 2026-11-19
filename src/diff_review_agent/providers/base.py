"""Base provider interface and configuration."""

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ProviderConfig:
    name: str
    api_key_env: str
    model_env: str
    base_url_env: str = ""


class Provider:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def get_config(self) -> ProviderConfig:
        return self.config

    def get_api_key(self) -> Optional[str]:
        return os.getenv(self.config.api_key_env)

    def get_model_name(self) -> str:
        return os.getenv(self.config.model_env, "gpt-4o-mini")

    def get_base_url(self) -> str:
        return os.getenv(self.config.base_url_env, "")

    def is_configured(self) -> bool:
        return bool(self.get_api_key())

    def request(self, payload: Any) -> Any:
        """Make API request to provider endpoint."""
        raise NotImplementedError("Subclasses must implement request method")


class BaseProvider(Provider):
    """Base class for all providers."""
    pass


class OpenAIProvider(BaseProvider):
    """OpenAI-compatible provider implementation."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.api_key = self.get_api_key()
        self.model_name = self.get_model_name()
        self.base_url = self.get_base_url()

    def is_configured(self) -> bool:
        return super().is_configured() and self.api_key is not None

    def request(self, payload: Any) -> Any:
        """Make API request to OpenAI-compatible endpoint."""
        if not self.is_configured():
            raise RuntimeError("Provider not configured - missing API key")
        # Placeholder for actual API call
        return {"status": "success", "data": payload}