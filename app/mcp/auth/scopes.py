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

# Shown on the consent page under "<client> will be able to": a title per
# scope and the detail beneath it. Wording only — the scopes themselves, and
# what each one permits, are defined above and enforced per tool.
SCOPE_TITLES: Dict[str, str] = {
    PROFILE_READ: "See your MITA profile",
    FINANCE_READ: "Read your finances in MITA",
    FINANCE_WRITE: "Update your MITA records when you ask",
    FEEDBACK_WRITE: "Send feedback to MITA when you ask",
    PROFILE_WRITE: "Change your usage-statistics setting when you ask",
}
SCOPE_DESCRIPTIONS: Dict[str, str] = {
    PROFILE_READ: "Your display name, a masked email address, currency and time zone",
    FINANCE_READ: (
        "Your expenses, budget plan, forecast, spending history, savings goals "
        "and recurring expenses"
    ),
    FINANCE_WRITE: (
        "It can record and correct expenses, update your budget profile, save a "
        "budget you reviewed, and add recurring expenses and savings goals"
    ),
    FEEDBACK_WRITE: "Only the message you ask it to send to the MITA team",
    PROFILE_WRITE: "Turn MITA usage statistics on or off for your account",
}
