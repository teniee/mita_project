"""Read-only query layer for MCP tools.

Every function here is synchronous, takes a SQLAlchemy ``Session`` and the
authenticated user's id as a Python argument (never from a tool input), and
returns plain dataclasses. Tools call them through ``AsyncSession.run_sync``.

One definition per fact:

* spend      — ``transactions`` with ``deleted_at IS NULL``, bucketed by the
               user's local day (``ledger.py``);
* allocation — ``daily_plan.planned_amount`` (``plan.py``);
* forecast   — ``compute_forecast`` over allocation + ledger spend.
"""
