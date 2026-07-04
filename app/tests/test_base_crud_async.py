"""
Regression tests for AsyncCRUDHelper.

Guards against the production bug where async goals routes awaited the sync
CRUDHelper (AsyncSession has no .query()), which 500'd every goal
get/update/delete endpoint, and delete called a method that didn't exist.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.base_crud import AsyncCRUDHelper
from app.db.models import Goal


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeAsyncSession:
    def __init__(self, resource=None):
        self.resource = resource
        self.committed = False
        self.deleted = None

    async def execute(self, query):
        return FakeResult(self.resource)

    async def commit(self):
        self.committed = True

    async def delete(self, obj):
        self.deleted = obj


@pytest.mark.asyncio
async def test_get_user_resource_found():
    goal = Goal(id=uuid4(), user_id=uuid4(), title="Test", target_amount=100)
    db = FakeAsyncSession(resource=goal)

    result = await AsyncCRUDHelper.get_user_resource_or_404(
        db, Goal, goal.id, goal.user_id
    )
    assert result is goal


@pytest.mark.asyncio
async def test_get_user_resource_not_found_raises_404():
    db = FakeAsyncSession(resource=None)

    with pytest.raises(HTTPException) as exc:
        await AsyncCRUDHelper.get_user_resource_or_404(
            db, Goal, uuid4(), uuid4(), "Goal not found"
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "Goal not found"


@pytest.mark.asyncio
async def test_delete_user_resource_soft_deletes_goal():
    goal = Goal(id=uuid4(), user_id=uuid4(), title="Test", target_amount=100)
    assert goal.deleted_at is None
    db = FakeAsyncSession(resource=goal)

    ok = await AsyncCRUDHelper.delete_user_resource_or_404(
        db, Goal, goal.id, goal.user_id
    )
    assert ok is True
    # Goal has deleted_at → must be soft-deleted, never hard-deleted
    assert goal.deleted_at is not None
    assert db.deleted is None
    assert db.committed is True


@pytest.mark.asyncio
async def test_delete_resource_hard_deletes_without_soft_delete_support():
    plain = SimpleNamespace(id=uuid4())  # no deleted_at attribute
    db = FakeAsyncSession(resource=plain)

    ok = await AsyncCRUDHelper.delete_resource(db, plain)
    assert ok is True
    assert db.deleted is plain
    assert db.committed is True
