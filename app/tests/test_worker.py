"""Smoke tests for the worker entry point and standard worker configuration."""


def test_worker_module_has_main():
    import app.worker as worker

    assert callable(worker.main)


def test_standard_worker_configs_cover_default_queue():
    from app.core.worker_manager import create_standard_worker_configs

    configs = create_standard_worker_configs()
    assert configs, "expected at least one standard worker config"
    assert any("default" in c.queues for c in configs)
    assert all(c.max_jobs > 0 for c in configs)
    assert all(c.job_timeout > 0 for c in configs)
