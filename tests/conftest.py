import os
import time

# Pin the test process to UTC for production parity (Railway runs TZ=UTC).
# asyncpg encodes NAIVE datetime params via the process-local timezone, so a
# developer machine in Europe/Sofia shifts naive-bound windows by 3h and
# date-boundary tests fail only between local midnight and 03:00.
# Mirrors app/tests/conftest.py; must run before any engine/datetime use.
os.environ["TZ"] = "UTC"
time.tzset()
