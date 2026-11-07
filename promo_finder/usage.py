"""Server-side Sarvam configuration for the editor interface."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


SARVAM_BASES = {"https://api.sarvam.ai/v1", "https://api.sarvam.ai/v2"}
SARVAM_MODELS = {"sarvam-105b", "sarvam-105b-conversations"}


@dataclass(frozen=True)
class SarvamConfig:
    api_key: str = field(default="", repr=False)
    model: str = "sarvam-105b"
    base_url: str = "https://api.sarvam.ai/v1"
    error: str = ""

    @classmethod
    def load(cls, get: Callable[[str], object]) -> "SarvamConfig":
        def text(name: str) -> str:
            value = get(name)
            return value.strip() if isinstance(value, str) else ""

        key = text("SARVAM_API_KEY")
        legacy_base = text("LLM_BASE_URL").rstrip("/")
        legacy = not key and legacy_base in SARVAM_BASES
        if legacy:
            key = text("LLM_API_KEY")
        model = text("SARVAM_MODEL") or "sarvam-105b"
        if model not in SARVAM_MODELS:
            return cls(error="The app owner needs to check the Sarvam model configuration.")
        explicit_base = text("SARVAM_BASE_URL").rstrip("/")
        if explicit_base and explicit_base not in SARVAM_BASES:
            return cls(error="The app owner needs to check the Sarvam endpoint configuration.")
        base = explicit_base or "https://api.sarvam.ai/v1"
        if model.endswith("-conversations"):
            base = "https://api.sarvam.ai/v1"
        return cls(api_key=key, model=model, base_url=base)

    @property
    def configured(self) -> bool:
        return bool(self.api_key) and not self.error
