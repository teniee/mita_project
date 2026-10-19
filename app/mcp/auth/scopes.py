"""The only scopes ChatGPT can be granted. Least privilege per area.

MITA's own API scopes (``write:transactions``, ``premium:*``, ``admin:*``…)
are never issued to ChatGPT. None of these scopes can move money: MITA has no
payment, transfer or bank capability at all.

Grants made before the write tools existed carry only the two read scopes;
a write tool then answers ``insufficient_scope`` and ChatGPT asks the user to
reconnect.
"""

from typing import Dict, Tuple

PROFILE_READ = "profile:read"
FINANCE_READ = "finance:read"
FINANCE_WRITE = "finance:write"
FEEDBACK_WRITE = "feedback:write"
PROFILE_WRITE = "profile:write"

SUPPORTED_SCOPES: Tuple[str, ...] = (
    PROFILE_READ,
    FINANCE_READ,
    FINANCE_WRITE,
    FEEDBACK_WRITE,
    PROFILE_WRITE,
)

WRITE_SCOPES: Tuple[str, ...] = (FINANCE_WRITE, FEEDBACK_WRITE, PROFILE_WRITE)

# Shown on the consent page.
SCOPE_DESCRIPTIONS: Dict[str, str] = {
    PROFILE_READ: "See your MITA display name, a masked e-mail, currency and timezone",
    FINANCE_READ: (
        "Read your MITA transactions, budget plan, forecast, spending history, "
        "savings goals and scheduled expenses"
    ),
    FINANCE_WRITE: (
        "When you ask: record and correct expenses, update your budget profile, "
        "save a budget you reviewed, and add recurring expenses and savings goals"
    ),
    FEEDBACK_WRITE: "Send feedback to the MITA team when you ask it to",
    PROFILE_WRITE: "Change your MITA usage-statistics setting when you ask it to",
}
