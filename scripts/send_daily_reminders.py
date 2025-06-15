from app.services.core.engine.cron_task_reminders import run_daily_email_reminders


def main() -> None:
    """Entry point for scheduled reminder emails."""
    run_daily_email_reminders()


if __name__ == "__main__":
    main()
