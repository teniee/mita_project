"""The only scopes ChatGPT can be granted. Read-only, least privilege.

MITA's own API scopes (``write:transactions``, ``premium:*``, ``admin:*``…)
are never issued to ChatGPT.
"""

from typing import Dict, Tuple

PROFILE_READ = "profile:read"
FINANCE_READ = "finance:read"

SUPPORTED_SCOPES: Tuple[str, ...] = (PROFILE_READ, FINANCE_READ)

# Shown on the consent page.
SCOPE_DESCRIPTIONS: Dict[str, str] = {
    PROFILE_READ: "See your MITA display name, a masked e-mail, currency and timezone",
    FINANCE_READ: (
        "Read your MITA transactions, budget plan, forecast, savings goals and "
        "scheduled expenses"
    ),
}
