"""
Regression tests: sync DB session must honor the DATABASE_URL's sslmode.

Bug context: `_initialize_sync_session` hard-coded `sslmode="require"`
("Force SSL for Supabase"), silently discarding the URL's own
`?sslmode=disable`. Every deployment whose Postgres runs without SSL —
CI service containers, docker-compose, private-network Postgres — failed
with "server does not support SSL, but SSL was required" on the entire
sync-session path (calendar routes, onboarding persistence, ...).
"""

from sqlalchemy.engine import make_url

from app.core.session import _resolve_sslmode


def _query(url: str):
    return make_url(url).query


class TestResolveSslmode:
    def test_explicit_disable_is_honored(self):
        q = _query("postgresql://test:test@localhost:5432/db?sslmode=disable")
        assert _resolve_sslmode(q) == "disable"

    def test_explicit_require_is_honored(self):
        q = _query("postgresql://u:p@host:5432/db?sslmode=require")
        assert _resolve_sslmode(q) == "require"

    def test_asyncpg_style_ssl_param(self):
        assert _resolve_sslmode(_query("postgresql://u:p@h/db?ssl=require")) == (
            "require"
        )
        assert _resolve_sslmode(_query("postgresql://u:p@h/db?ssl=disable")) == (
            "disable"
        )
        assert _resolve_sslmode(_query("postgresql://u:p@h/db?ssl=true")) == "require"
        assert _resolve_sslmode(_query("postgresql://u:p@h/db?ssl=false")) == "disable"

    def test_verify_modes_pass_through(self):
        for mode in ("allow", "prefer", "verify-ca", "verify-full"):
            q = _query(f"postgresql://u:p@h/db?sslmode={mode}")
            assert _resolve_sslmode(q) == mode

    def test_defaults_to_require_when_unspecified(self):
        """Hosted Postgres (Supabase/Railway) keeps the safe default."""
        assert _resolve_sslmode(_query("postgresql://u:p@h/db")) == "require"

    def test_unknown_value_falls_back_to_require(self):
        q = _query("postgresql://u:p@h/db?sslmode=bogus")
        assert _resolve_sslmode(q) == "require"
