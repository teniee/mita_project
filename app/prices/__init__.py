"""Local retail prices — the architecture, its security controls and its
fallbacks, with no paid provider active (owner brief 2026-11-09, task 4).

MITA holds official statistics (``app/regional``) and, separately, could hold
retail price observations. The two never mix: a statistic is a national
average, a retail price is one product at one merchant on one day.

Nothing here can reach a paid service until the owner approves the provider,
the API access, a monthly spend cap, a per-user quota and the privacy and
data-handling rules (``approval.PriceSearchApproval``). Until then every
lookup answers ``no_verified_price`` and no price is ever invented.

A search result is never a recorded expense, never a budget line and never
an instruction: it is untrusted data, checked field by field
(``validation.verify``) before anything of it is shown, and shown with its
source link.
"""
