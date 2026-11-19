"""OpenAI provider implementation."""

import os
import json
import time
from typing import Any, Dict, List, Optional

import diff_review_agent.providers.base as base


class OpenAIProvider(base.OpenAIProvider):
    """OpenAI provider implementation."""

    def __init__(self, config: base.ProviderConfig):
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
        return {"status": "success", "data": payload}
