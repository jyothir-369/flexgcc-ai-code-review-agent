"""Base provider interface for LLM integrations."""
from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional


class LLMMessage:
    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


class LLMResponse:
    def __init__(
        self,
        content: str = "",
        finish_reason: str = "stop",
        error: Optional[str] = None,
    ) -> None:
        self.content = content
        self.finish_reason = finish_reason
        self.error = error

    @property
    def is_error(self) -> bool:
        return self.error is not None


class BaseProvider(abc.ABC):
    """Abstract base for all LLM providers."""

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Return True if the provider has credentials available."""
        ...

    @abc.abstractmethod
    def complete(
        self,
        messages: List[LLMMessage],
        max_tokens: int = 1000,
        timeout: int = 30,
    ) -> LLMResponse:
        """Send a chat-completion request and return the response."""
        ...
