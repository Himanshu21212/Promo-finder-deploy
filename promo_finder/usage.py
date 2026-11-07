"""Sarvam setup and session usage. A balance snapshot is an estimate, never a live wallet."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from typing import Callable


SARVAM_BASES = {"https://api.sarvam.ai/v1", "https://api.sarvam.ai/v2"}
SARVAM_MODELS = {"sarvam-105b", "sarvam-105b-conversations"}
BILLING_URL = "https://indus.sarvam.ai"


@dataclass(frozen=True)
class SarvamConfig:
    api_key: str = field(default="", repr=False)
    model: str = "sarvam-105b"
    base_url: str = "https://api.sarvam.ai/v2"
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
        base = "https://api.sarvam.ai/v1" if model.endswith("-conversations") else (
            legacy_base if legacy else "https://api.sarvam.ai/v2")
        return cls(api_key=key, model=model, base_url=base)

    @property
    def configured(self) -> bool:
        return bool(self.api_key) and not self.error

    @property
    def scope(self) -> str:
        # Used only to isolate browser-session accounting when the server credential changes.
        return hashlib.sha256(self.api_key.encode()).hexdigest()


def _money(value: object) -> Decimal | None:
    try:
        amount = Decimal(str(value))
        return amount if amount.is_finite() and amount >= 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


@dataclass
class UsageLedger:
    """Stores counters only, scoped to one browser session and one credential.

    Recording a run replaces its cumulative counters, so UI rerenders never charge twice.
    Missing usage makes a remaining-balance estimate unavailable rather than inventing spend.
    """
    runs: dict[str, dict] = field(default_factory=dict)
    snapshot_balance: Decimal | None = None
    snapshot_spend: Decimal = Decimal(0)
    snapshot_unreported: int = 0
    snapshot_at: str = ""
    last_error_code: int = 0

    def record(self, run_id: str, stats: dict) -> None:
        self.runs[run_id] = {k: _count(stats.get(k)) for k in (
            "calls", "usage_calls", "prompt_tokens", "completion_tokens")}
        self.runs[run_id]["cost"] = _money(stats.get("estimated_cost_inr"))
        self.last_error_code = _count(stats.get("last_error_code"))

    @property
    def spend(self) -> Decimal:
        return sum((r["cost"] or Decimal(0) for r in self.runs.values()), Decimal(0))

    def total(self, key: str) -> int:
        return sum(r.get(key, 0) for r in self.runs.values())

    @property
    def unreported(self) -> int:
        return sum(max(r["calls"] - (r["usage_calls"] if r["cost"] is not None else 0), 0)
                   for r in self.runs.values())

    def set_snapshot(self, value: object) -> None:
        amount = _money(value)
        if amount is None:
            raise ValueError("Enter a valid, non-negative balance from Sarvam.")
        self.snapshot_balance = amount
        self.snapshot_spend = self.spend
        self.snapshot_unreported = self.unreported
        self.snapshot_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    @property
    def remaining(self) -> Decimal | None:
        if self.snapshot_balance is None or self.unreported > self.snapshot_unreported:
            return None
        return max(self.snapshot_balance - (self.spend - self.snapshot_spend), Decimal(0))
