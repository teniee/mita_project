import os

import psycopg2


def explain_slow_queries(limit: int = 10) -> None:
    """Print slow queries ordered by total time using pg_stat_statements."""
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL environment variable is required")

    query = (
        "SELECT query, total_time, calls "
        "FROM pg_stat_statements "
        "ORDER BY total_time DESC "
        "LIMIT %s;"
    )

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()
            for i, row in enumerate(rows, 1):
                print(
                    f"{i}. {row[0][:100]}\n   total_time={row[1]:.2f}s calls={row[2]}"
                )
    finally:
        conn.close()


if __name__ == "__main__":
    limit_env = os.getenv("TOP_N", "10")
    explain_slow_queries(int(limit_env))
