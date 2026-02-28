"""Unified LLM client using LiteLLM + Instructor.

LiteLLM provides a single interface to 100+ LLM providers.
Instructor adds Pydantic-validated structured output with retries.

Falls back to raw LiteLLM when Instructor is not available.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMResponse:
    """Raw LLM response wrapper."""

    content: str


class LiteLLMClient:
    """Unified LLM client backed by LiteLLM.

    Supports:
    - complete(): raw text completion
    - create(): Instructor-powered Pydantic-validated structured output
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_retries: int = 2,
        temperature: float = 0.0,
    ) -> None:
        self._model = (
            model
            or os.getenv("DARU_OPENAI_MODEL")
            or os.getenv("OPENAI_API_KEY")
        )
        self._api_key = (
            api_key
            or os.getenv("DARU_OPENAI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        self._base_url = base_url or os.getenv("DARU_OPENAI_BASE_URL")
        self._max_retries = max_retries
        self._temperature = temperature
        self._available = self._api_key is not None

        self._configure_litellm()

        self._instructor_client: Any | None = None
        if self._available:
            self._init_instructor()

    @staticmethod
    def _configure_litellm() -> None:
        """Set LiteLLM module-level config."""
        try:
            import litellm
            litellm.drop_params = True
        except ImportError:
            pass

    def _init_instructor(self) -> None:
        """Initialize Instructor-patched LiteLLM client."""
        try:
            import instructor
            import litellm

            if self._api_key:
                litellm.api_key = self._api_key
            if self._base_url:
                litellm.api_base = self._base_url

            self._instructor_client = instructor.from_litellm(
                litellm.acompletion
            )
        except ImportError:
            logger.warning(
                "instructor or litellm not installed — "
                "structured output unavailable, falling back to raw completion"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize instructor client: {e}")

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def model(self) -> str:
        return self._model

    async def complete(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
    ) -> LLMResponse:
        """Raw text completion."""
        if not self._available:
            raise RuntimeError("LLM client not configured (no API key)")

        try:
            import litellm

            kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "temperature": self._temperature,
            }

            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["api_base"] = self._base_url
            if response_format:
                kwargs["response_format"] = response_format

            response = await litellm.acompletion(**kwargs)
            content = response.choices[0].message.content or ""
            return LLMResponse(content=content)

        except ImportError:
            raise RuntimeError(
                "litellm not installed — run: pip install litellm"
            )

    async def create(
        self,
        response_model: type[T],
        messages: list[dict[str, str]],
        max_retries: int | None = None,
    ) -> T:
        """Structured output using Instructor + Pydantic validation."""
        if not self._instructor_client:
            raise RuntimeError(
                "Instructor client not available — "
                "install: pip install instructor litellm"
            )

        return await self._instructor_client.chat.completions.create(
            model=self._model,
            response_model=response_model,
            messages=messages,
            max_retries=max_retries or self._max_retries,
            temperature=self._temperature,
        )


_llm_client: LiteLLMClient | None = None


def get_llm_client() -> LiteLLMClient | None:
    """Get the global LiteLLM client singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LiteLLMClient()
    return _llm_client if _llm_client.is_available else None
