"""
Unified budget threshold constants for MITA.

Single source of truth for all budget warning levels.
"""

# Percentage of budget spent that triggers each level
THRESHOLD_SAFE: float = 0.70       # Below 70%: all good
THRESHOLD_CAUTION: float = 0.70    # At 70%: gentle heads-up
THRESHOLD_WARNING: float = 0.80    # At 80%: clear warning
THRESHOLD_DANGER: float = 0.90     # At 90%: danger zone
THRESHOLD_EXCEEDED: float = 1.00   # At 100%: budget exceeded

# After how many days to send follow-up reminder if user ignored alert
REMINDER_FOLLOWUP_DAYS: int = 3
