import datetime
import io
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest
from starlette.datastructures import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.transactions.routes import create_transaction_standardized, process_receipt
from app.api.transactions.schemas import TxnIn


@pytest.mark.asyncio
async def test_create_transaction_updates_plan(monkeypatch):
    """Test that creating a transaction works end-to-end with standardized route."""
    from app.api.transactions import routes as txn_routes

    # Mock validation functions to pass through
    monkeypatch.setattr(txn_routes, "validate_required_fields", lambda *a, **kw: None)
    monkeypatch.setattr(txn_routes, "validate_amount", lambda amt, **kw: float(amt))

    # Mock add_transaction (called via db.run_sync)
    dummy_result = {"id": "t123", "category": "food", "amount": 12.5}
    monkeypatch.setattr(txn_routes, "add_transaction", lambda user, txn, session: dummy_result)

    db = create_autospec(AsyncSession, instance=True)
    # run_sync calls the lambda with a sync session
    db.run_sync = AsyncMock(side_effect=lambda fn: fn(MagicMock()))

    user = SimpleNamespace(id="u1", timezone="UTC")
    request = MagicMock()
    data = TxnIn(
        category="food",
        amount=12.5,
        spent_at=datetime.datetime(2025, 1, 1),
    )

    result = await create_transaction_standardized(request, data, user=user, db=db)
    assert result is not None


@pytest.mark.asyncio
async def test_process_receipt(monkeypatch):
    """Test receipt processing submits OCR task."""
    from app.api.transactions import routes as txn_routes

    # Mock task_manager.submit_ocr_task to avoid Redis dependency
    dummy_task_info = SimpleNamespace(
        task_id="task-123",
        status=SimpleNamespace(value="pending"),
        estimated_completion="30s",
    )
    monkeypatch.setattr(
        txn_routes.task_manager, "submit_ocr_task", lambda **kw: dummy_task_info
    )

    file = UploadFile(
        filename="r.jpg",
        file=io.BytesIO(b"data"),
        headers={"content-type": "image/jpeg"},
    )
    user = SimpleNamespace(id="u1")
    db = create_autospec(AsyncSession, instance=True)

    result = await process_receipt(file=file, user=user, db=db)
    # success_response wraps in JSONResponse
    import json

    body = json.loads(result.body.decode())
    assert body["data"]["task_id"] == "task-123"
    assert body["data"]["status"] == "pending"
