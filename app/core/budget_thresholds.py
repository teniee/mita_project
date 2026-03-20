"""
Unified budget threshold constants for MITA.

Single source of truth for all budget warning levels.
"""

# Percentage of budget spent that triggers each level
THRESHOLD_SAFE: float = 0.70       # Below 70%: all good (green)
THRESHOLD_WARNING: float = 0.80    # At 80%: clear warning — push notification sent
THRESHOLD_DANGER: float = 0.90     # At 90%: danger zone — push notification sent
THRESHOLD_EXCEEDED: float = 1.00   # At 100%: budget exceeded — push notification sent
THRESHOLD_MODERATE: float = 0.50   # Below 50%: comfortable buffer (informational, no push)

# After how many days to send follow-up reminder if user ignored alert
REMINDER_FOLLOWUP_DAYS: int = 3

# ---------------------------------------------------------------------------
# Velocity alert thresholds
# velocity_ratio = (monthly_spent / days_elapsed) / (monthly_planned / days_in_month)
# ---------------------------------------------------------------------------
VELOCITY_WATCH: float = 1.20      # 120 %: gentle heads-up
VELOCITY_WARNING: float = 1.50    # 150 %: budget at real risk
VELOCITY_CRITICAL: float = 2.00   # 200 %: emergency

# Minimum elapsed days before velocity alerts are meaningful
VELOCITY_MIN_DAYS: int = 3

# Don't re-send same category velocity alert within this window
VELOCITY_ALERT_COOLDOWN_HOURS: int = 24

# Positive win detection: day is "good" when spent < this fraction of planned
WIN_DAILY_UNDER_PCT: float = 0.80

# Days of consecutive good-days that trigger a win notification
WIN_STREAK_DAYS: int = 7
