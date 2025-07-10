#!/usr/bin/env python
"""Utility to run Alembic migrations."""
import os
import subprocess

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

subprocess.run(["alembic", "upgrade", "head"], check=True)
