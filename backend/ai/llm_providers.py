"""LLM Provider Module.
===================

Abstraction layer for LLM providers:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""

    provider: str = "openai"
    model: str = "gpt-4"
    api_key: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 60
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class LLMResponse:
    """Response from LLM."""

    content: str
    model: str
    usage: dict[str, int]
    finish_reason: str
    raw_response: Any | None = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        """Initialize LLM provider.

        Args:
            config: LLM configuration

        """
        self.config = config

    @abstractmethod
    async def generate(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> LLMResponse:
        """Generate completion from prompt.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            **kwargs: Additional parameters

        Returns:
            LLMResponse

        """
        pass

    @abstractmethod
    async def generate_stream(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> AsyncIterator[str]:
        """Generate streaming completion.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            **kwargs: Additional parameters

        Yields:
            Completion tokens

        """
        pass

    @abstractmethod
    async def chat(self, messages: list[dict[str, str]], **kwargs) -> LLMResponse:
        """Multi-turn chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional parameters

        Returns:
            LLMResponse

        """
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider (GPT-4, GPT-3.5)."""

    def __init__(self, config: LLMConfig):
        """Initialize OpenAI provider.

        Args:
            config: LLM configuration with OpenAI API key

        """
        super().__init__(config)
        self._client = None

    def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=self.config.api_key,
                    timeout=self.config.timeout,
                )
            except ImportError:
                raise ImportError("openai package not installed. Install with: pip install openai")
        return self._client

    async def generate(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> LLMResponse:
        """Generate completion using OpenAI."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return await self.chat(messages, **kwargs)

    async def generate_stream(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> AsyncIterator[str]:
        """Generate streaming completion."""
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = await client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            messages=messages,
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat(self, messages: list[dict[str, str]], **kwargs) -> LLMResponse:
        """Multi-turn chat completion."""
        client = self._get_client()

        for attempt in range(self.config.retry_attempts):
            try:
                response = await client.chat.completions.create(
                    model=kwargs.get("model", self.config.model),
                    messages=messages,
                    temperature=kwargs.get("temperature", self.config.temperature),
                    max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                    top_p=kwargs.get("top_p", self.config.top_p),
                    frequency_penalty=kwargs.get(
                        "frequency_penalty", self.config.frequency_penalty
                    ),
                    presence_penalty=kwargs.get("presence_penalty", self.config.presence_penalty),
                )

                return LLMResponse(
                    content=response.choices[0].message.content,
                    model=response.model,
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    },
                    finish_reason=response.choices[0].finish_reason,
                    raw_response=response,
                )

            except Exception as e:
                logger.warning(f"OpenAI API error (attempt {attempt + 1}): {e}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise


class AnthropicProvider(LLMProvider):
    """Anthropic API provider (Claude)."""

    def __init__(self, config: LLMConfig):
        """Initialize Anthropic provider.

        Args:
            config: LLM configuration with Anthropic API key

        """
        super().__init__(config)
        self._client = None

    def _get_client(self):
        """Get or create Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic

                self._client = AsyncAnthropic(
                    api_key=self.config.api_key,
                    timeout=self.config.timeout,
                )
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. Install with: pip install anthropic"
                )
        return self._client

    async def generate(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> LLMResponse:
        """Generate completion using Anthropic."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, system_prompt=system_prompt, **kwargs)

    async def generate_stream(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> AsyncIterator[str]:
        """Generate streaming completion."""
        client = self._get_client()

        messages = [{"role": "user", "content": prompt}]

        async with client.messages.stream(
            model=kwargs.get("model", self.config.model),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            system=system_prompt or "",
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def chat(
        self, messages: list[dict[str, str]], system_prompt: str | None = None, **kwargs
    ) -> LLMResponse:
        """Multi-turn chat completion."""
        client = self._get_client()

        # Convert messages format if needed
        anthropic_messages = []
        for msg in messages:
            if msg["role"] != "system":
                anthropic_messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                    }
                )
            elif not system_prompt:
                system_prompt = msg["content"]

        for attempt in range(self.config.retry_attempts):
            try:
                response = await client.messages.create(
                    model=kwargs.get("model", self.config.model),
                    max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                    system=system_prompt or "",
                    messages=anthropic_messages,
                    temperature=kwargs.get("temperature", self.config.temperature),
                )

                return LLMResponse(
                    content=response.content[0].text,
                    model=response.model,
                    usage={
                        "prompt_tokens": response.usage.input_tokens,
                        "completion_tokens": response.usage.output_tokens,
                        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                    },
                    finish_reason=response.stop_reason,
                    raw_response=response,
                )

            except Exception as e:
                logger.warning(f"Anthropic API error (attempt {attempt + 1}): {e}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise


def get_provider(config: LLMConfig) -> LLMProvider:
    """Factory function to get appropriate LLM provider.

    Args:
        config: LLM configuration

    Returns:
        LLM provider instance

    """
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
    }

    provider_class = providers.get(config.provider.lower())
    if provider_class is None:
        raise ValueError(f"Unknown provider: {config.provider}")

    return provider_class(config)
