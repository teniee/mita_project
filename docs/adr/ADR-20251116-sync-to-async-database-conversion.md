# ADR-20251116: Sync to Async Database Conversion

**Date:** 2025-11-16
**Status:** In Progress
**Author:** MITA CTO Engineering Team

## Context & User Impact

20+ router files in MITA currently use synchronous SQLAlchemy ORM with `Session` and `get_db`, which blocks the asyncio event loop on every database query. This causes:

- **Performance degradation**: Blocking I/O prevents concurrent request handling
- **Poor scalability**: Thread pool exhaustion under load
- **Increased latency**: P95/P99 response times suffer
- **Resource waste**: Idle threads waiting for database responses

**User Impact:**
- Dashboard loads slowly (main screen affected)
- Transaction list lags
- Budget calculations timeout under moderate load
- Mobile app shows spinners longer than necessary

## Technical Plan

### Affected Components

**CRITICAL (Main User Flows):**
1. `/app/api/dashboard/routes.py` - Main screen (highest priority)
2. `/app/api/transactions/routes.py` - Transaction list/create
3. `/app/api/budget/routes.py` - Budget management
4. `/app/api/analytics/routes.py` - Analytics dashboard

**HIGH:**
5. `/app/api/challenge/routes.py`
6. `/app/api/ai/routes.py`
7. `/app/api/goals/routes.py`
8. `/app/api/expense/routes.py`

**MEDIUM:**
9. `/app/api/behavior/routes.py`
10. `/app/api/cohort/routes.py`
11. `/app/api/calendar/routes.py`
12. `/app/api/insights/routes.py`
13. `/app/api/mood/routes.py`
14. `/app/api/habits/routes.py`

### API/Data Contract Changes

**None - This is an internal implementation change only.**

All public API contracts remain identical:
- Request/response schemas unchanged
- Endpoint URLs unchanged
- HTTP status codes unchanged
- Error responses unchanged

### Database Migration Plan

**No migrations required** - this is a code-level change only.

Existing async infrastructure already in place:
- `app/core/async_session.py` provides `get_async_db()`
- SQLAlchemy 2.0 async engine configured
- Connection pooling configured for asyncpg

### Conversion Pattern

**Before (Sync):**
```python
from app.core.session import get_db
from sqlalchemy.orm import Session

@router.get("/endpoint")
async def endpoint(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.id == user_id).all()  # BLOCKS!
    db.commit()
```

**After (Async):**
```python
from app.core.async_session import get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

@router.get("/endpoint")
async def endpoint(db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    users = result.scalars().all()
    await db.commit()
```

### Query Pattern Conversions

| Sync Pattern | Async Pattern |
|--------------|---------------|
| `db.query(Model).filter(...).all()` | `result = await db.execute(select(Model).where(...)); result.scalars().all()` |
| `db.query(Model).first()` | `result = await db.execute(select(Model)); result.scalar_one_or_none()` |
| `db.query(func.sum(col)).scalar()` | `result = await db.execute(select(func.sum(col))); result.scalar()` |
| `db.add(obj); db.commit()` | `db.add(obj); await db.commit()` |
| `db.refresh(obj)` | `await db.refresh(obj)` |
| `db.rollback()` | `await db.rollback()` |

### Eager Loading Conversions

**Sync:**
```python
from sqlalchemy.orm import joinedload
participations = db.query(ChallengeParticipation).options(
    joinedload(ChallengeParticipation.challenge)
).all()
```

**Async:**
```python
from sqlalchemy.orm import selectinload, joinedload
result = await db.execute(
    select(ChallengeParticipation).options(
        joinedload(ChallengeParticipation.challenge)
    )
)
participations = result.unique().scalars().all()  # .unique() required for joins!
```

### Feature Flag Strategy

**Not applicable** - internal change with identical external behavior.

Testing will validate correctness before deployment.

### Performance Considerations

**Expected Improvements:**
- **Throughput**: +300-500% concurrent requests
- **P95 latency**: -40-60% (from non-blocking I/O)
- **Resource usage**: -50% thread pool utilization

**Monitoring:**
- Track `http_request_duration_seconds` for affected endpoints
- Monitor `db_connection_pool_size` and `db_connection_pool_available`
- Alert on increased error rates

### Security Considerations

**No security changes** - same authentication, authorization, input validation.

Async code uses identical:
- JWT scope checking
- Input validation (Pydantic)
- SQL injection protection (parameterized queries)

### Testing Plan

**Per-File Testing:**
1. **Syntax check**: `python3 -m py_compile <file>`
2. **Unit tests**: Run existing tests for affected endpoints
3. **Integration tests**: Verify database operations
4. **Performance tests**: Compare sync vs async latency

**Pre-Deployment Validation:**
- All endpoints return correct data structure
- Error handling unchanged
- Transactions rollback correctly on errors
- Connection pool doesn't leak

### Rollout Strategy

**Phase 1: CRITICAL files (4 files)**
- Convert dashboard, transactions, budget, analytics
- Deploy to staging
- Run smoke tests
- Performance benchmark vs production sync version

**Phase 2: HIGH files (4 files)**
- Convert challenge, ai, goals, expense
- Staged rollout with monitoring

**Phase 3: MEDIUM files (~6 files)**
- Batch conversion
- Full regression test suite

**Deployment:**
- Code changes only (no DB migration)
- Zero-downtime deployment
- Canary: 5% → 25% → 100%
- Rollback: revert code deploy (instant)

### Rollback Strategy

**Immediate rollback available:**
- Revert code deployment (no DB state change)
- Sync `get_db` dependency still exists in codebase
- Previous deployment remains valid

**Rollback triggers:**
- Error rate >2% on converted endpoints
- P95 latency increase >20%
- Connection pool exhaustion
- Any data inconsistency

## Decision

**Approved for implementation** with phased rollout starting with CRITICAL files.

**Success Criteria:**
- Zero regressions in API contracts
- All unit/integration tests pass
- Performance improvement confirmed
- No increase in error rates

## Consequences

**Positive:**
- Significant performance improvement
- Better resource utilization
- Improved scalability
- Modern async/await patterns

**Negative:**
- Code churn across 20+ files
- Requires careful testing
- Team must understand async patterns

**Migration Path:**
- Old sync code remains in git history
- Feature-flagged rollback possible
- Gradual migration reduces risk

## References

- SQLAlchemy 2.0 Async Documentation: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- MITA Architecture: `/Users/mikhail/StudioProjects/mita_project/README.md`
- Async Session Implementation: `/Users/mikhail/StudioProjects/mita_project/app/core/async_session.py`
