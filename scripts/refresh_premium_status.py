from app.services.core.engine.cron_task_subscription_refresh import (
    refresh_premium_status,
)


def main() -> None:
    """Entry point for scheduled premium status refresh."""
    refresh_premium_status()


if __name__ == "__main__":
    main()
