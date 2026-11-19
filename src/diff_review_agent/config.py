"""Configuration loading and runtime settings."""

import os
from pathlib import Path

# Required environment variables (names only; values not hardcoded)
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_OPENAI_MODEL = "OPENAI_MODEL"
ENV_OPENAI_BASE_URL = "OPENAI_BASE_URL"

# Default settings (overridable via env vars or .env file)
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

    def get(self, key: str):
        return self.settings[key]

config = Config()

def get_config():
    return config