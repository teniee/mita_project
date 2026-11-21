"""The owner's approval of a paid price search, as configuration.

Paid search stays off until EVERY part of the approval exists: the provider,
the API access (the NAME of the environment variable holding the key, never
the key), a monthly spend cap, a per-user quota, the allowed domains, how
long a verified price may be kept, and the version of the approved privacy
text. A partial or malformed approval is no approval: ``from_env`` returns
None and every lookup answers ``no_verified_price``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Mapping, Optional, Tuple

PROVIDERS = ("openai_web_search",)
MAX_ALLOWED_DOMAINS = 100  # OpenAI web_search filters.allowed_domains limit
PREFIX = "MITA_PRICE_SEARCH_"


@dataclass(frozen=True)
class PriceSearchApproval:
    provider: str
    model: str
    api_key_env: str
    monthly_cap_usd: Decimal
    estimated_cost_per_lookup_usd: Decimal
    per_user_daily_lookups: int
    allowed_domains: Tuple[str, ...]
    retention_days: int  # 0: a verified price is shown, never kept
    privacy_rules_version: str
    approved_on: date

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> Optional["PriceSearchApproval"]:
        def get(name: str) -> str:
            return (environ.get(PREFIX + name) or "").strip()

        if get("APPROVED").lower() != "yes":
            return None
        try:
            provider = get("PROVIDER")
            domains = tuple(
                d.strip().lower()
                for d in get("ALLOWED_DOMAINS").split(",")
                if d.strip()
            )
            approval = cls(
                provider=provider,
                model=get("MODEL"),
                api_key_env=get("API_KEY_ENV"),
                monthly_cap_usd=Decimal(get("MONTHLY_CAP_USD")),
                estimated_cost_per_lookup_usd=Decimal(get("COST_PER_LOOKUP_USD")),
                per_user_daily_lookups=int(get("PER_USER_DAILY")),
                allowed_domains=domains,
                retention_days=int(get("RETENTION_DAYS")),
                privacy_rules_version=get("PRIVACY_VERSION"),
                approved_on=date.fromisoformat(get("APPROVED_ON")),
            )
        except (InvalidOperation, ValueError):
            return None
        return approval if approval.complete() else None

    def complete(self) -> bool:
        return (
            self.provider in PROVIDERS
            and bool(self.model)
            and bool(self.api_key_env)
            and self.monthly_cap_usd > 0
            and self.estimated_cost_per_lookup_usd > 0
            and self.per_user_daily_lookups > 0
            and 0 < len(self.allowed_domains) <= MAX_ALLOWED_DOMAINS
            and all("/" not in d and ":" not in d for d in self.allowed_domains)
            and self.retention_days >= 0
            and bool(self.privacy_rules_version)
        )
