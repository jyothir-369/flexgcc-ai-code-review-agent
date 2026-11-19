"""Configuration loading and runtime settings."""

import os
from pathlib import Path

# Provider selection (names only; values not hardcoded)
ENV_LLM_PROVIDER = "LLM_PROVIDER"

# Required environment variables (names only; values not hardcoded)
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_OPENAI_MODEL = "OPENAI_MODEL"
ENV_OPENAI_BASE_URL = "OPENAI_BASE_URL"

# Gemini provider environment variable names
ENV_GEMINI_API_KEY = "GEMINI_API_KEY"
ENV_GEMINI_MODEL = "GEMINI_MODEL"
ENV_GEMINI_BASE_URL = "GEMINI_BASE_URL"

# Supported provider identifiers
SUPPORTED_PROVIDERS = ("openai", "gemini")

# Default provider when LLM_PROVIDER is unset
DEFAULT_PROVIDER = "openai"

# Default settings (overridable via exported environment variables)
DEFAULTS = {
    "diff_max_bytes": 1024 * 1024,  # 1 MB
    "diff_max_files": 50,
    "excerpt_max_chars": 500,
    "max_context_tokens": 2000,
    "max_response_tokens": 1000,
    "max_tool_calls": 10,
    "max_retries": 1,
    "timeout_seconds": 30,
}

class Config:
    def __init__(self):
        self.settings = DEFAULTS.copy()
        self._load_from_env()
        self._load_provider()

    def _load_from_env(self):
        """Load settings from environment variables."""
        for key, default in DEFAULTS.items():
            env_key = f"DIFF_REVIEW_AGENT_{key.upper()}"
            val = os.environ.get(env_key)
            if val is not None:
                try:
                    self.settings[key] = type(default)(val)
                except ValueError:
                    pass  # Keep default if invalid

    def _load_provider(self):
        """Load provider selection from environment (case-insensitive)."""
        val = os.environ.get(ENV_LLM_PROVIDER)
        if val is None:
            self.settings["llm_provider"] = DEFAULT_PROVIDER
        else:
            self.settings["llm_provider"] = val.strip().lower() or DEFAULT_PROVIDER

    def get(self, key: str, default=None):
        """Return a setting, or ``default`` when the key is absent.

        Callers that omit ``default`` still raise KeyError for unknown keys,
        matching the previous contract.
        """
        if default is None and key not in self.settings:
            return self.settings[key]
        return self.settings.get(key, default)

config = Config()

def get_config():
    return config