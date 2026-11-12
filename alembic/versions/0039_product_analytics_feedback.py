"""ChatGPT app: product feedback, and pseudonymous product analytics.

Revision ID: 0039
Revises: 0038
Create Date: 2026-10-12

Additive only. Written by the MCP service; read by the team (Metabase or
``scripts/mcp/analytics_report.py``) through the ``analytics`` schema only.

* ``product_feedback`` (public): what a user explicitly chose to send, with
  their user id so it is deleted with the account. Internal triage fields
  (status, theme, internal_notes) are never shown to users.
* ``analytics_identities`` (public): user id -> pseudonymous ``user_key``
  (an HMAC under ``MCP_ANALYTICS_SECRET``). Cascades with the user, and
  ``analytics.events.user_key`` cascades from it, so deleting an account —
  or turning usage statistics off — deletes every event linked to that
  person. The analytics reader role never gets access to this table.
* ``analytics.events``: one row per tool call or lifecycle event. Columns are
  fixed; ``properties`` is an allow-listed JSON object (enforced in
  ``app/mcp/analytics.py``). No amounts, merchants, titles, free text, raw
  session ids or user ids.
* ``analytics.segment_thresholds``: the numbers behind lifecycle segments,
  editable with an UPDATE.
* Views: user_daily, feature_daily, activity_daily (DAU/WAU/MAU/WFAU),
  activation (funnel), retention_weekly, feature_adoption, user_segments,
  reliability_daily, registrations_daily, feedback, storage.
"""

from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

# Features that count as "financially active" (WFAU) — product-analytics.md.
FINANCIAL_FEATURES = (
    "'transactions','summary','spending','budget_status','forecast',"
    "'budget_plan','recurring','goals','history'"
)
ALL_FEATURES = (
    "('account'),('setup'),('summary'),('transactions'),('spending'),"
    "('budget_status'),('forecast'),('budget_plan'),('recurring'),('goals'),"
    "('history'),('feedback'),('privacy')"
)

VIEWS = {
    "tool_calls": """
        SELECT id, occurred_at, (occurred_at AT TIME ZONE 'UTC')::date AS day,
               user_key, session_key, feature, tool_name, intent_code,
               status, error_code, latency_ms, locale
        FROM analytics.events
        WHERE event_name IN ('tool_call_succeeded', 'tool_call_failed')
    """,
    "user_daily": """
        SELECT day, user_key,
               count(DISTINCT session_key) AS sessions,
               count(*) AS tool_calls,
               count(*) FILTER (WHERE status = 'ok') AS successful_calls,
               count(*) FILTER (WHERE status = 'error') AS failed_calls,
               count(DISTINCT feature) AS active_features,
               bool_or(status = 'ok' AND feature IN (%(financial)s)) AS financially_active
        FROM analytics.tool_calls
        WHERE user_key IS NOT NULL
        GROUP BY day, user_key
    """,
    "feature_daily": """
        SELECT day, feature,
               count(DISTINCT user_key) AS users,
               count(*) AS calls,
               count(*) FILTER (WHERE status = 'ok') AS successes,
               count(*) FILTER (WHERE status = 'error') AS failures,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50_latency_ms,
               percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms
        FROM analytics.tool_calls
        GROUP BY day, feature
    """,
    "activity_daily": """
        WITH days AS (
            SELECT generate_series(
                (now() AT TIME ZONE 'UTC')::date - 89,
                (now() AT TIME ZONE 'UTC')::date, interval '1 day')::date AS day
        )
        SELECT d.day,
               count(DISTINCT u.user_key) FILTER (WHERE u.day = d.day) AS dau,
               count(DISTINCT u.user_key) FILTER (WHERE u.day > d.day - 7) AS wau,
               count(DISTINCT u.user_key) AS mau,
               count(DISTINCT u.user_key) FILTER (
                   WHERE u.day > d.day - 7 AND u.financially_active) AS wfau,
               sum(u.tool_calls) FILTER (WHERE u.day = d.day) AS calls,
               sum(u.sessions) FILTER (WHERE u.day = d.day) AS sessions
        FROM days d
        LEFT JOIN analytics.user_daily u ON u.day > d.day - 30 AND u.day <= d.day
        GROUP BY d.day
    """,
    "user_firsts": """
        SELECT user_key,
               min(occurred_at) AS first_seen,
               min(occurred_at) FILTER (WHERE event_name = 'account_created') AS account_created,
               min(occurred_at) FILTER (WHERE event_name = 'oauth_connected') AS oauth_connected,
               min(occurred_at) FILTER (WHERE event_name = 'onboarding_started') AS setup_started,
               min(occurred_at) FILTER (WHERE event_name IN
                   ('financial_profile_created', 'financial_profile_updated')) AS profile_saved,
               min(occurred_at) FILTER (WHERE event_name = 'onboarding_completed') AS setup_completed,
               min(occurred_at) FILTER (WHERE event_name = 'budget_previewed') AS budget_previewed,
               min(occurred_at) FILTER (WHERE event_name IN ('budget_saved', 'budget_replaced')) AS budget_saved,
               min(occurred_at) FILTER (WHERE event_name IN
                   ('transaction_created', 'transaction_batch_created')) AS first_transaction,
               count(*) FILTER (WHERE event_name = 'transaction_created')
                 + coalesce(sum((properties->>'item_count')::int)
                     FILTER (WHERE event_name = 'transaction_batch_created'), 0)
                   AS transactions_recorded
        FROM analytics.events
        WHERE user_key IS NOT NULL
        GROUP BY user_key
    """,
    "activation": """
        SELECT (first_seen AT TIME ZONE 'UTC')::date AS cohort_day,
               count(*) AS users,
               count(oauth_connected) AS oauth_connected,
               count(account_created) AS accounts_created,
               count(setup_started) AS setup_started,
               count(profile_saved) AS profile_saved,
               count(budget_previewed) AS budget_previewed,
               count(budget_saved) AS budget_saved,
               count(first_transaction) AS first_transaction,
               count(setup_completed) AS setup_completed
        FROM analytics.user_firsts
        GROUP BY 1
    """,
    "retention_weekly": """
        WITH cohorts AS (
            SELECT user_key, date_trunc('week', first_seen AT TIME ZONE 'UTC')::date AS cohort_week
            FROM analytics.user_firsts
        ), weeks AS (
            SELECT DISTINCT user_key, date_trunc('week', day)::date AS week
            FROM analytics.user_daily
        )
        SELECT c.cohort_week,
               ((w.week - c.cohort_week) / 7) AS week_number,
               (SELECT count(*) FROM cohorts c2 WHERE c2.cohort_week = c.cohort_week) AS users_total,
               count(DISTINCT w.user_key) AS users_retained
        FROM cohorts c JOIN weeks w ON w.user_key = c.user_key AND w.week >= c.cohort_week
        GROUP BY c.cohort_week, w.week
    """,
    "retention_days": """
        SELECT f.user_key, f.first_seen,
               EXISTS (SELECT 1 FROM analytics.user_daily u WHERE u.user_key = f.user_key
                       AND u.day = (f.first_seen AT TIME ZONE 'UTC')::date + 1) AS d1,
               EXISTS (SELECT 1 FROM analytics.user_daily u WHERE u.user_key = f.user_key
                       AND u.day = (f.first_seen AT TIME ZONE 'UTC')::date + 7) AS d7,
               EXISTS (SELECT 1 FROM analytics.user_daily u WHERE u.user_key = f.user_key
                       AND u.day = (f.first_seen AT TIME ZONE 'UTC')::date + 30) AS d30,
               (now() - f.first_seen) >= interval '2 days' AS d1_eligible,
               (now() - f.first_seen) >= interval '8 days' AS d7_eligible,
               (now() - f.first_seen) >= interval '31 days' AS d30_eligible
        FROM analytics.user_firsts f
    """,
    "feature_adoption": """
        WITH features(feature) AS (VALUES %(all_features)s),
        recent AS (
            SELECT * FROM analytics.tool_calls
            WHERE occurred_at >= now() - interval '30 days' AND status = 'ok'
        ),
        mau AS (SELECT count(DISTINCT user_key) AS n FROM recent),
        per_user AS (
            SELECT feature, user_key, count(*) AS calls, count(DISTINCT day) AS days
            FROM recent WHERE user_key IS NOT NULL GROUP BY feature, user_key
        ),
        previous AS (
            SELECT DISTINCT feature, user_key FROM analytics.tool_calls
            WHERE status = 'ok' AND user_key IS NOT NULL
              AND occurred_at >= now() - interval '60 days'
              AND occurred_at < now() - interval '30 days'
        )
        SELECT f.feature,
               (SELECT n FROM mau) AS eligible_users,
               count(p.user_key) AS users_used,
               CASE WHEN (SELECT n FROM mau) > 0
                    THEN round(100.0 * count(p.user_key) / (SELECT n FROM mau), 1) END AS adoption_percent,
               (SELECT count(*) FROM recent r WHERE r.feature = f.feature) AS calls,
               CASE WHEN count(p.user_key) > 0
                    THEN round(sum(p.calls)::numeric / count(p.user_key), 2) END AS calls_per_user,
               CASE WHEN count(p.user_key) > 0
                    THEN round(100.0 * count(*) FILTER (WHERE p.days >= 2) / count(p.user_key), 1)
               END AS repeat_percent,
               CASE WHEN (SELECT count(*) FROM previous pr WHERE pr.feature = f.feature) > 0
                    THEN round(100.0 * count(*) FILTER (WHERE EXISTS (
                        SELECT 1 FROM previous pr WHERE pr.feature = f.feature
                        AND pr.user_key = p.user_key))
                      / (SELECT count(*) FROM previous pr WHERE pr.feature = f.feature), 1)
               END AS d30_repeat_percent
        FROM features f
        LEFT JOIN per_user p ON p.feature = f.feature
        GROUP BY f.feature
    """,
    "user_segments": """
        WITH t AS (SELECT name, value FROM analytics.segment_thresholds),
        activity AS (
            SELECT user_key,
                   count(DISTINCT day) FILTER (
                       WHERE day > (now() AT TIME ZONE 'UTC')::date - 30 AND financially_active) AS active_days_30,
                   count(DISTINCT day) FILTER (
                       WHERE day > (now() AT TIME ZONE 'UTC')::date - 60
                         AND day <= (now() AT TIME ZONE 'UTC')::date - 30 AND financially_active) AS active_days_prev_30,
                   max(day) AS last_active
            FROM analytics.user_daily GROUP BY user_key
        )
        SELECT f.user_key,
               CASE
                 WHEN f.first_seen > now() - make_interval(days => (SELECT value FROM t WHERE name = 'new_days')) THEN 'NEW'
                 WHEN a.active_days_30 >= (SELECT value FROM t WHERE name = 'power_active_days') THEN 'POWER'
                 WHEN a.active_days_30 >= (SELECT value FROM t WHERE name = 'engaged_active_days') THEN 'ENGAGED'
                 WHEN a.last_active IS NULL
                   OR a.last_active <= (now() AT TIME ZONE 'UTC')::date - (SELECT value FROM t WHERE name = 'dormant_days') THEN 'DORMANT'
                 WHEN a.active_days_prev_30 >= (SELECT value FROM t WHERE name = 'engaged_active_days')
                  AND a.last_active <= (now() AT TIME ZONE 'UTC')::date - (SELECT value FROM t WHERE name = 'at_risk_days') THEN 'AT_RISK'
                 WHEN f.setup_completed IS NOT NULL AND (f.budget_saved IS NOT NULL
                   OR f.transactions_recorded >= (SELECT value FROM t WHERE name = 'activated_transactions')) THEN 'ACTIVATED'
                 ELSE 'CASUAL'
               END AS segment,
               coalesce(a.active_days_30, 0) AS active_days_30,
               a.last_active
        FROM analytics.user_firsts f LEFT JOIN activity a ON a.user_key = f.user_key
    """,
    "reliability_daily": """
        SELECT day, tool_name,
               count(*) AS calls,
               count(*) FILTER (WHERE status = 'ok') AS successes,
               count(*) FILTER (WHERE status = 'error') AS failures,
               count(*) FILTER (WHERE error_code = 'validation') AS validation_errors,
               count(*) FILTER (WHERE error_code = 'invalid_arguments') AS rejected_arguments,
               count(*) FILTER (WHERE error_code IN ('auth', 'forbidden')) AS auth_errors,
               count(*) FILTER (WHERE error_code = 'unavailable') AS unavailable_errors,
               count(*) FILTER (WHERE error_code = 'internal') AS internal_errors,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50_latency_ms,
               percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms
        FROM analytics.tool_calls
        GROUP BY day, tool_name
    """,
    "registrations_daily": """
        SELECT (created_at AT TIME ZONE 'UTC')::date AS day, count(*) AS registrations
        FROM public.users
        GROUP BY 1
    """,
    "feedback": """
        SELECT f.id, f.created_at, i.user_key, f.type, f.feature_area, f.message,
               f.rating, f.status, f.source, f.theme, f.internal_notes
        FROM public.product_feedback f
        LEFT JOIN public.analytics_identities i ON i.user_id = f.user_id
    """,
    "storage": """
        SELECT c.relname AS relation, n.nspname AS schema_name,
               c.reltuples::bigint AS estimated_rows,
               pg_total_relation_size(c.oid) AS total_bytes,
               pg_indexes_size(c.oid) AS index_bytes
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r' AND n.nspname IN ('public', 'analytics')
          AND c.relname IN ('transactions', 'daily_plan', 'goals', 'scheduled_expenses',
                            'users', 'product_feedback', 'events',
                            'mcp_idempotency_keys', 'mcp_oauth_refresh_tokens')
    """,
}

VIEW_ORDER = (
    "tool_calls",
    "user_daily",
    "feature_daily",
    "activity_daily",
    "user_firsts",
    "activation",
    "retention_weekly",
    "retention_days",
    "feature_adoption",
    "user_segments",
    "reliability_daily",
    "registrations_daily",
    "feedback",
    "storage",
)


def upgrade():
    op.execute(
        """
        CREATE TABLE product_feedback (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL DEFAULT now(),
            type varchar(20) NOT NULL CHECK (type IN
                ('feature_request', 'bug_report', 'confusing', 'praise', 'other')),
            feature_area varchar(20) NOT NULL CHECK (feature_area IN
                ('transactions', 'budget', 'history', 'goals', 'recurring', 'setup', 'other')),
            message text NOT NULL CHECK (char_length(message) BETWEEN 1 AND 2000),
            rating smallint CHECK (rating BETWEEN 1 AND 5),
            status varchar(16) NOT NULL DEFAULT 'new' CHECK (status IN
                ('new', 'reviewed', 'planned', 'resolved', 'closed')),
            source varchar(16) NOT NULL DEFAULT 'chatgpt',
            theme varchar(64),
            internal_notes text
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_product_feedback_created ON product_feedback (created_at)"
    )
    op.execute("CREATE INDEX ix_product_feedback_user ON product_feedback (user_id)")
    op.execute(
        """
        CREATE TABLE analytics_identities (
            user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            user_key varchar(32) NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE SCHEMA analytics")
    op.execute(
        """
        CREATE TABLE analytics.events (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            occurred_at timestamptz NOT NULL,
            user_key varchar(32) REFERENCES public.analytics_identities(user_key)
                ON DELETE CASCADE,
            session_key varchar(32),
            event_name varchar(48) NOT NULL CHECK (event_name ~ '^[a-z_]{3,48}$'),
            feature varchar(32),
            tool_name varchar(48),
            intent_code varchar(48),
            status varchar(16) NOT NULL CHECK (status IN ('ok', 'error')),
            error_code varchar(32),
            latency_ms integer CHECK (latency_ms >= 0),
            surface varchar(16) NOT NULL,
            locale varchar(16),
            server_version varchar(16) NOT NULL,
            tool_contract_version varchar(16) NOT NULL,
            properties jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(properties) = 'object')
        )
        """
    )
    op.execute("CREATE INDEX ix_events_occurred_at ON analytics.events (occurred_at)")
    op.execute(
        "CREATE INDEX ix_events_user_key_occurred ON analytics.events "
        "(user_key, occurred_at) WHERE user_key IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_events_name_occurred ON analytics.events (event_name, occurred_at)"
    )
    op.execute(
        """
        CREATE TABLE analytics.segment_thresholds (
            name varchar(32) PRIMARY KEY,
            value integer NOT NULL CHECK (value >= 0),
            meaning text NOT NULL
        )
        """
    )
    op.execute(
        """
        INSERT INTO analytics.segment_thresholds (name, value, meaning) VALUES
          ('new_days', 7, 'NEW: first seen less than this many days ago'),
          ('activated_transactions', 3, 'ACTIVATED: setup completed and a saved budget or at least this many recorded expenses'),
          ('engaged_active_days', 8, 'ENGAGED: at least this many financially active days in the last 30'),
          ('power_active_days', 20, 'POWER: at least this many financially active days in the last 30'),
          ('at_risk_days', 14, 'AT_RISK: engaged in the previous 30 days but inactive for at least this many days'),
          ('dormant_days', 30, 'DORMANT: no activity for at least this many days')
        """
    )
    params = {"financial": FINANCIAL_FEATURES, "all_features": ALL_FEATURES}
    for name in VIEW_ORDER:
        op.execute(f"CREATE VIEW analytics.{name} AS {VIEWS[name] % params}")


def downgrade():
    op.execute("DROP SCHEMA analytics CASCADE")
    op.execute("DROP TABLE analytics_identities")
    op.execute("DROP TABLE product_feedback")
