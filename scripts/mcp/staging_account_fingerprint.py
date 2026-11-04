"""Read-only fingerprint of ONE staging account: proves a release left it alone.

Prints, per table, how many of the account's rows there are and a SHA-256
digest of them — never an amount, a name, an e-mail, a merchant, a line label
or an id. Run it before and after a migration, a deploy and the smoke tests:
equal digests mean those rows were not changed (a different digest names the
table, and the account's own use of ChatGPT in between is a legitimate cause).

    railway run --project <staging project id> --environment staging \\
        --service Postgres -- \\
        python scripts/mcp/staging_account_fingerprint.py \\
        --email-file <0600 file holding the account's e-mail> \\
        [--host-port 127.0.0.1:15432]   # through an SSH tunnel to the private host

* The database URL comes from the environment (``DATABASE_URL``, injected by
  ``railway run``); it is never an argument and never printed. ``--host-port``
  only swaps the host and port (a tunnel's local end), keeping the rest.
* The e-mail is read from a file so it is not typed into a command or a chat.
* Refuses to run unless ``RAILWAY_PROJECT_ID`` is the staging project, or
  ``--local`` against a ``test_*`` database on localhost. Production's project
  is refused by id, whatever else is set.
* One ``READ ONLY`` transaction with a statement timeout; nothing is written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text

STAGING_PROJECT_ID = "497476f2-de93-44b7-b170-2b175c8d5621"
PRODUCTION_PROJECT_ID = "d44d0580-3476-4e46-bc4c-b2d95dac64cd"

# Per table: the rows that belong to the account. Users: the account's own
# row without the columns any sign-in rewrites (last_login, the lockout
# counter), so signing in to ChatGPT does not look like a change.
ACCOUNT_ROWS = {
    "users": (
        "SELECT id, email, country, annual_income, monthly_income, savings_goal,"
        " currency, region, timezone, token_version, has_onboarded, name,"
        " budget_method, created_at FROM users WHERE id = :uid"
    ),
    "transactions": "SELECT * FROM transactions WHERE user_id = :uid",
    "daily_plan": "SELECT * FROM daily_plan WHERE user_id = :uid",
    "scheduled_expenses": "SELECT * FROM scheduled_expenses WHERE user_id = :uid",
    "goals": "SELECT * FROM goals WHERE user_id = :uid",
    "mcp_user_profiles": "SELECT * FROM mcp_user_profiles WHERE user_id = :uid",
    "mcp_budget_lines": "SELECT * FROM mcp_budget_lines WHERE user_id = :uid",
    "obligation_payments": "SELECT * FROM obligation_payments WHERE user_id = :uid",
    "spending_patterns": "SELECT * FROM spending_patterns WHERE user_id = :uid",
}


class Refused(RuntimeError):
    pass


def database_url(host_port: str | None) -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise Refused("DATABASE_URL is not set (run it through `railway run`).")
    parts = urlsplit(url)
    if host_port:
        credentials = parts.netloc.rsplit("@", 1)[0] if "@" in parts.netloc else ""
        netloc = f"{credentials}@{host_port}" if credentials else host_port
        parts = parts._replace(netloc=netloc)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        parts = parts._replace(scheme="postgresql+psycopg2")
    return urlunsplit(parts)


def check_target(url: str, local: bool) -> str:
    project = os.environ.get("RAILWAY_PROJECT_ID", "").strip()
    if project == PRODUCTION_PROJECT_ID:
        raise Refused("this is the production project: refused.")
    if project == STAGING_PROJECT_ID:
        return "staging"
    if local:
        parts = urlsplit(url)
        database = parts.path.lstrip("/")
        if parts.hostname in ("localhost", "127.0.0.1") and database.startswith("test"):
            return "local test database"
        raise Refused("--local needs a test_* database on localhost.")
    raise Refused(
        "not inside the staging project's Railway context "
        "(RAILWAY_PROJECT_ID is missing or another project)."
    )


def digest(rows) -> str:
    h = hashlib.sha256()
    for row in rows:
        h.update(json.dumps(row, sort_keys=True, default=str).encode())
        h.update(b"\n")
    return h.hexdigest()[:16]


def fingerprint(conn, email: str) -> dict:
    conn.execute(text("SET TRANSACTION READ ONLY"))
    conn.execute(text("SET LOCAL statement_timeout = '15s'"))
    uid = conn.execute(
        text("SELECT id FROM users WHERE lower(email) = :email"), {"email": email}
    ).scalar()
    if uid is None:
        return {"account": "not found"}
    present = {
        name
        for (name,) in conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        )
    }
    out = {
        "account": "found",
        "alembic": conn.execute(text("SELECT version_num FROM alembic_version"))
        .scalars()
        .all(),
    }
    for table, query in ACCOUNT_ROWS.items():
        if table not in present:
            out[table] = "table absent"
            continue
        rows = [
            dict(r._mapping) for r in conn.execute(text(query), {"uid": uid}).fetchall()
        ]
        rows.sort(key=lambda r: json.dumps(r, sort_keys=True, default=str))
        entry = {"rows": len(rows), "digest": digest(rows)}
        if table == "transactions":
            entry["live"] = sum(1 for r in rows if r.get("deleted_at") is None)
        if table == "daily_plan":
            nov = [r for r in rows if str(r.get("date", ""))[:7] == "2026-11"]
            entry["2026-11"] = {"rows": len(nov), "digest": digest(nov)}
        out[table] = entry
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--email-file", required=True, type=Path)
    parser.add_argument("--host-port", help="host:port of a tunnel's local end")
    parser.add_argument("--local", action="store_true")
    args = parser.parse_args(argv)
    try:
        email = args.email_file.read_text().strip().lower()
        if "@" not in email:
            raise Refused("the e-mail file does not hold an e-mail address.")
        url = database_url(args.host_port)
        target = check_target(url, args.local)
    except (Refused, OSError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    engine = create_engine(url, pool_pre_ping=False)
    with engine.connect() as conn:
        with conn.begin():
            result = fingerprint(conn, email)
    engine.dispose()
    print(json.dumps({"target": target, **result}, indent=1, sort_keys=True))
    return 0 if result.get("account") == "found" else 1


if __name__ == "__main__":
    sys.exit(main())
