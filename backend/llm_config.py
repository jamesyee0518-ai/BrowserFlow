"""LLM configuration for workflow engine integration."""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel


class LLMProviderConfig(BaseModel):
    provider: Literal["openai", "anthropic", "azure", "deepseek"] = "openai"
    model: str = "gpt-4o"
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.0


class LLMConfig:
    _instance: LLMConfig | None = None

    def __init__(self) -> None:
        self.primary = LLMProviderConfig(
            provider=os.environ.get("LLM_PROVIDER", "openai"),
            model=os.environ.get("LLM_MODEL", "gpt-4o"),
            api_key=os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("LLM_BASE_URL"),
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "4096")),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.0")),
        )
        self.script_generation = LLMProviderConfig(
            provider=os.environ.get("SCRIPT_GEN_LLM_PROVIDER", self.primary.provider),
            model=os.environ.get("SCRIPT_GEN_LLM_MODEL", self.primary.model),
            api_key=os.environ.get("SCRIPT_GEN_LLM_API_KEY", self.primary.api_key),
            base_url=os.environ.get("SCRIPT_GEN_LLM_BASE_URL", self.primary.base_url),
            max_tokens=int(os.environ.get("SCRIPT_GEN_LLM_MAX_TOKENS", "8192")),
            temperature=0.0,
        )
        self.extraction = LLMProviderConfig(
            provider=os.environ.get("EXTRACTION_LLM_PROVIDER", self.primary.provider),
            model=os.environ.get("EXTRACTION_LLM_MODEL", "gpt-4o-mini"),
            api_key=os.environ.get("EXTRACTION_LLM_API_KEY", self.primary.api_key),
            base_url=os.environ.get("EXTRACTION_LLM_BASE_URL", self.primary.base_url),
            max_tokens=int(os.environ.get("EXTRACTION_LLM_MAX_TOKENS", "2048")),
            temperature=0.0,
        )

    @classmethod
    def get(cls) -> LLMConfig:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def is_configured(self) -> bool:
        return self.primary.api_key is not None
