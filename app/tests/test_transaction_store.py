from app.services.core.engine.transaction_store import create_transaction


def test_transaction_store_add_get():
    calendar = {}
    tx = create_transaction("cal-1", "2025-04-01", "Test", 123, "Utilities", calendar)
    assert tx is not None
