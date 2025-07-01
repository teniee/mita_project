from app.services.core.engine.cron_task_ai_advice import run_ai_advice_batch


def main():
    """Entry point for scheduled AI push advice."""
    run_ai_advice_batch()


if __name__ == "__main__":
    main()

