"""Configuration: model provider selection via environment variables.

Providers:
  - ollama     (default): local, free. LiteLLM -> Ollama at OLLAMA_HOST.
  - openrouter: OpenRouter via LiteLLM. Needs OPENROUTER_API_KEY.
  - demo:      built-in scripted policy model + fixture issues. Fully offline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    provider: str = "ollama"
    model: str = "qwen2.5"
    ollama_host: str = "http://localhost:11434"
    openrouter_api_key: str = ""
    openrouter_model: str = "qwen/qwen-2.5-72b-instruct"
    github_token: str = ""
    apply_changes: bool = False  # never write to GitHub unless explicitly enabled

    @classmethod
    def from_env(cls) -> "Settings":
        provider = os.environ.get("TRIAGEPILOT_PROVIDER", "ollama").strip().lower()
        if provider not in ("ollama", "openrouter", "demo"):
            raise ValueError(f"Unknown TRIAGEPILOT_PROVIDER={provider!r}; want ollama|openrouter|demo")
        return cls(
            provider=provider,
            model=os.environ.get("TRIAGEPILOT_MODEL", "qwen2.5"),
            ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            openrouter_model=os.environ.get("OPENROUTER_MODEL", "qwen/qwen-2.5-72b-instruct"),
            github_token=os.environ.get("GITHUB_TOKEN", ""),
            apply_changes=os.environ.get("TRIAGEPILOT_APPLY", "0") == "1",
        )

    @property
    def demo_mode(self) -> bool:
        return self.provider == "demo"


def build_model(settings: Settings):
    """Return a Strands model for the configured provider."""
    if settings.provider == "demo":
        from .demo_model import ScriptedTriageModel

        return ScriptedTriageModel()

    # Lazy import: litellm is only needed for real LLM providers.
    from strands.models.litellm import LiteLLMModel

    if settings.provider == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "TRIAGEPILOT_PROVIDER=openrouter requires OPENROUTER_API_KEY to be set."
            )
        return LiteLLMModel(
            model_id=f"openrouter/{settings.openrouter_model}",
            params={
                "api_key": settings.openrouter_api_key,
                "api_base": "https://openrouter.ai/api/v1",
            },
        )

    # ollama (default): free, local. LiteLLM speaks the Ollama API natively.
    return LiteLLMModel(
        model_id=f"ollama/{settings.model}",
        params={"api_base": settings.ollama_host},
    )
