#!/usr/bin/env python3
"""CI entry point for the production-target guard.

Usage: python scripts/_target_guard_cli.py <base-url>
Exit 0 when the target is safe to write to, 2 when it is missing or production.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _target_guard import ProductionTargetError, assert_writable_target  # noqa: E402


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        safe = assert_writable_target(target, purpose="CI deployed-smoke job")
    except ProductionTargetError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"target OK: {safe}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
