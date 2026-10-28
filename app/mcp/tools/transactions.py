from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, List, Optional

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult
from pydantic import BaseModel, ConfigDict, Field

from app.mcp import analytics, idempotency
from app.mcp.auth.scopes import FINANCE_READ, FINANCE_WRITE
from app.mcp.categories import label as category_label
from app.mcp.crypto import CursorPosition
from app.mcp.errors import ValidationError
from app.mcp.queries import ledger
from app.mcp.queries import setup as setup_queries
from app.mcp.queries.periods import resolve_date_range
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import (
    RecordedTransactionOut,
    SpendingBreakdownOut,
    TransactionChangeOut,
    TransactionsOut,
    TransactionsRecordedOut,
)
from app.mcp.serializers import (
    money,
    spending_breakdown_out,
    transaction_ref,
    transactions_out,
)
from app.mcp.tools.common import (
    NO_MONEY_MOVEMENT,
    READ_ONLY_DISCLAIMER,
    read_only_annotations,
    tool_meta,
    write_annotations,
)
from app.mcp.tools.inputs import (
    CATEGORY_HELP,
    EntryMethod,
    ExpenseCategory,
    IdempotencyKey,
    Merchant,
    TransactionAmount,
)
from app.mcp.ui import component_callable_meta
from app.mcp.writes import transactions as writes

MAX_BATCH = 25

StartDate = Annotated[
    Optional[date],
    Field(
        description="First local day to include (YYYY-MM-DD). Defaults to 29 days before end_date."
    ),
]
EndDate = Annotated[
    Optional[date],
    Field(
        description="Last local day to include (YYYY-MM-DD). Defaults to today in the user's timezone."
    ),
]
ExpenseDate = Annotated[
    Optional[date],
    Field(
        description=(
            "Local calendar day of the expense (YYYY-MM-DD) in the user's timezone. "
            "Omit for today. Resolve words like 'yesterday' against the user's "
            "today; never a future date."
        )
    ),
]
Ref = Annotated[
    str,
    Field(
        min_length=4,
        max_length=128,
        description="The expense's `ref` from list_transactions or from the result that recorded it.",
    ),
]

LIST_DESCRIPTION = (
    "List the user's recorded expenses in MITA for a date range, newest first. Each "
    "item has the local date, amount, currency, category, merchant (when recorded) "
    "and an opaque `ref` used only to correct or delete that expense; free-text "
    "notes, receipts and locations are never returned. Optional filters: category "
    "(exact code, e.g. 'groceries') and merchant (case-insensitive contains). The "
    "merchant filter searches only THIS user's own expenses by the merchant text they "
    "recorded: MITA has no access to anyone else's account, so a person's name finds "
    "only this user's expenses recorded with that name, never that person's data. Dates are "
    "calendar days in the user's timezone; the range may span at most 366 days. "
    "Returns at most `limit` items plus the count and total of ALL matching "
    "expenses; when has_more is true, call again with `cursor` = next_cursor (same "
    "dates and filters) to get the next page — keep paging when the user asked "
    "for all of them. Deleted transactions are excluded. MITA records expenses "
    "only (no income or account balances). " + READ_ONLY_DISCLAIMER
)

BREAKDOWN_DESCRIPTION = (
    "Total the user's recorded MITA expenses by category for a date range: per-category "
    "total, transaction count and share of all spending, largest first, plus the overall "
    "total. Use it for 'where did my money go' questions. Dates are calendar days in the "
    "user's timezone (default: the last 30 days, at most 366). Deleted transactions are "
    "excluded. It reports what was spent, not what was budgeted — use get_budget_status "
    "for the plan. " + READ_ONLY_DISCLAIMER
)

ADD_DESCRIPTION = (
    "Record ONE expense the user made, e.g. 'Spent €36.80 at Lidl on groceries "
    "today'. Saves it in the user's MITA account (it is part of every future "
    "conversation) and updates this month's budget plan. Use the "
    "amount exactly as stated, in the user's MITA currency. If the amount or the "
    "category is unclear, ask before recording; never invent a merchant. For "
    "several expenses at once use add_transactions. For an expense read from a "
    "receipt photo in this chat, set entry_method 'receipt_image'; MITA never "
    "receives the image. The result includes a `ref` to correct the expense with "
    "update_transaction. " + NO_MONEY_MOVEMENT
)

ADD_MANY_DESCRIPTION = (
    "Record SEVERAL expenses in one step (up to 25), e.g. 'Today: €8 coffee, €55 fuel "
    "and €74 at Lidl', or the lines of a receipt photo the user attached. All are "
    "saved together or none is: if any item is invalid, nothing is recorded and the "
    "error names the item. Same rules per item as add_transaction (amounts as "
    "stated, ask when a category or total is unclear). Every item has its own "
    "category: give each receipt line the category of what it is, not of the shop — "
    "a supermarket receipt can mix groceries with household goods (shopping) or "
    "medicine (healthcare). MITA has no alcohol or tobacco category: drinks bought "
    "in a shop count as groceries unless the user picks another category. "
    + NO_MONEY_MOVEMENT
)

UPDATE_DESCRIPTION = (
    "Correct one recorded expense the user says is wrong — amount, category, date or "
    "merchant — identified by its `ref`. Changes only the fields sent and overwrites "
    "their previous values; the month's budget plan is recalculated. Confirm which "
    "expense the user means first (use list_transactions to find it). "
    + NO_MONEY_MOVEMENT
)

DELETE_DESCRIPTION = (
    "Delete one recorded expense the user wants removed (for example a duplicate or "
    "a mistake), identified by its `ref`. It disappears from all totals and the "
    "month's plan is recalculated. Confirm the exact expense with the user before "
    "deleting. Deleting an already deleted expense changes nothing. "
    + NO_MONEY_MOVEMENT
)


class ExpenseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: TransactionAmount
    category: Annotated[ExpenseCategory, Field(description=CATEGORY_HELP)]
    date: ExpenseDate = None
    merchant: Merchant = None


def _filter_digest(start, end, category, merchant) -> bytes:
    text = f"{start}|{end}|{category or ''}|{(merchant or '').lower()}"
    return hashlib.sha256(text.encode()).digest()[:8]


def _epoch_us(instant: datetime) -> int:
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    delta = instant - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def _from_epoch_us(value: int) -> datetime:
    from datetime import timedelta

    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=value)


def _recorded(keys, ctx, row) -> RecordedTransactionOut:
    return RecordedTransactionOut(
        ref=transaction_ref(keys, ctx, row.id),
        date=writes.local_day(ctx, row),
        amount=money(Decimal(str(row.amount))),
        currency=(row.currency or ctx.currency).upper(),
        category=row.category,
        category_label=category_label(row.category),
        merchant=(row.merchant or "").strip() or None,
    )


def register(server: MCPServer, runtime: McpRuntime) -> None:
    keys = runtime.data_keys

    @server.tool(
        name="list_transactions",
        title="List MITA transactions",
        description=LIST_DESCRIPTION,
        annotations=read_only_annotations("List MITA transactions"),
        meta=tool_meta(
            FINANCE_READ,
            "Reading your transactions…",
            "Read your transactions",
            # The calendar component lists a selected date's expenses with it.
            **component_callable_meta(),
        ),
    )
    async def list_transactions(
        ctx: Context,
        start_date: StartDate = None,
        end_date: EndDate = None,
        category: Annotated[
            Optional[str],
            Field(
                description="Only this MITA category, e.g. 'groceries', 'dining', 'rent', 'transportation'.",
                min_length=1,
                max_length=50,
                pattern=r"^[A-Za-z][A-Za-z_ &-]*$",
            ),
        ] = None,
        merchant: Annotated[
            Optional[str],
            Field(
                description="Only merchants whose name contains this text (case-insensitive).",
                min_length=1,
                max_length=100,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum transactions to return (1-200).", ge=1, le=200),
        ] = 50,
        cursor: Annotated[
            Optional[str],
            Field(
                description="next_cursor from the previous page of the same query.",
                min_length=8,
                max_length=128,
            ),
        ] = None,
    ) -> Annotated[CallToolResult, TransactionsOut]:
        def body(session, user_ctx):
            start, end = resolve_date_range(user_ctx, start_date, end_date)
            cat = category.strip().lower() if category else None
            merch = merchant.strip() if merchant else None
            digest = _filter_digest(start, end, cat, merch)
            after = None
            if cursor is not None:
                position = keys.open_cursor(user_ctx.user_id, cursor)
                if position is None or position.filter_digest != digest:
                    raise ValidationError(
                        "This cursor does not belong to this query. Repeat the "
                        "same dates and filters, or start again without a cursor."
                    )
                after = (_from_epoch_us(position.spent_at_us), position.transaction_id)
            page = ledger.list_entries(
                session,
                user_ctx,
                start,
                end,
                category=cat,
                merchant=merch,
                limit=limit,
                after=after,
            )
            next_cursor = None
            if page.has_more and page.entries:
                last = page.entries[-1]
                next_cursor = keys.cursor(
                    user_ctx.user_id,
                    CursorPosition(
                        _epoch_us(last.spent_at), last.transaction_id, digest
                    ),
                )
            return transactions_out(
                user_ctx,
                start,
                end,
                page,
                keys=keys,
                next_cursor=next_cursor,
                merchant_filter=merch,
            )

        return await runtime.execute(
            "list_transactions",
            FINANCE_READ,
            body,
            ctx=ctx,
            intent="list_transactions",
        )

    @server.tool(
        name="get_spending_breakdown",
        title="Get spending by category",
        description=BREAKDOWN_DESCRIPTION,
        annotations=read_only_annotations("Get spending by category"),
        meta=tool_meta(
            FINANCE_READ, "Totalling your spending…", "Totalled your spending"
        ),
    )
    async def get_spending_breakdown(
        ctx: Context,
        start_date: StartDate = None,
        end_date: EndDate = None,
    ) -> Annotated[CallToolResult, SpendingBreakdownOut]:
        def body(session, user_ctx):
            start, end = resolve_date_range(user_ctx, start_date, end_date)
            totals = ledger.totals_by_category(session, user_ctx, start, end)
            others = ledger.other_currencies_in_range(session, user_ctx, start, end)
            return spending_breakdown_out(user_ctx, start, end, totals, others)

        return await runtime.execute(
            "get_spending_breakdown",
            FINANCE_READ,
            body,
            ctx=ctx,
            intent="category_breakdown",
        )

    async def _record(
        session,
        user_ctx,
        call,
        items: List[ExpenseItem],
        key: str,
        entry: str,
        tool: str,
    ) -> TransactionsRecordedOut:
        expenses = [
            writes.Expense(
                amount=item.amount,
                category=item.category,
                day=item.date,
                merchant=item.merchant,
            )
            for item in items
        ]

        def write(s) -> TransactionsRecordedOut:
            writes.require_currency(user_ctx, setup_queries.currency_set(user_ctx))
            request = {
                "items": [
                    [str(e.amount), e.category, str(e.day or ""), e.merchant or ""]
                    for e in expenses
                ],
                "entry": entry,
            }
            claim = idempotency.claim(
                s,
                user_id=user_ctx.user_id,
                operation=tool,
                session_digest=call.session_digest,
                key=key,
                request=request,
                now=call.now,
            )
            if claim.is_replay:
                analytics.mark_replayed()
                rows = writes.load_owned(
                    s, user_ctx, claim.replay_ids, include_deleted=True
                )
                status = "already_recorded"
                notes = [
                    "These expenses were already recorded by an earlier identical "
                    "request; nothing new was written."
                ]
                if any(r.deleted_at is not None for r in rows):
                    notes.append("Some of them were deleted since.")
            else:
                rows = writes.build_rows(user_ctx, expenses, call.now)
                writes.insert(s, rows)
                claim.complete([r.id for r in rows])
                s.commit()
                status = "recorded"
                notes = []
                if len(rows) == 1:
                    analytics.emit("transaction_created", entry_method=entry)
                else:
                    analytics.emit(
                        "transaction_batch_created",
                        entry_method=entry,
                        item_count=len(rows),
                    )
                if entry == "receipt_image":
                    analytics.emit("receipt_flow_completed", item_count=len(rows))
            total = sum((Decimal(str(r.amount)) for r in rows), Decimal("0.00"))
            return TransactionsRecordedOut(
                status=status,
                currency=user_ctx.currency,
                transactions=[_recorded(keys, user_ctx, r) for r in rows],
                count=len(rows),
                total=money(total),
                month_to_date_spent=money(writes.month_to_date_spent(s, user_ctx)),
                notes=notes,
            )

        return await session.run_sync(write)

    @server.tool(
        name="add_transaction",
        title="Record an expense in MITA",
        description=ADD_DESCRIPTION,
        annotations=write_annotations(
            "Record an expense in MITA", destructive=False, idempotent=True
        ),
        meta=tool_meta(
            FINANCE_WRITE, "Recording your expense…", "Recorded your expense"
        ),
    )
    async def add_transaction(
        ctx: Context,
        amount: TransactionAmount,
        category: Annotated[ExpenseCategory, Field(description=CATEGORY_HELP)],
        idempotency_key: IdempotencyKey,
        date: ExpenseDate = None,
        merchant: Merchant = None,
        entry_method: EntryMethod = "conversation",
    ) -> Annotated[CallToolResult, TransactionsRecordedOut]:
        item = ExpenseItem(
            amount=amount, category=category, date=date, merchant=merchant
        )

        async def body(session, user_ctx, call):
            return await _record(
                session,
                user_ctx,
                call,
                [item],
                idempotency_key,
                entry_method,
                "add_transaction",
            )

        return await runtime.execute_write(
            "add_transaction",
            FINANCE_WRITE,
            body,
            ctx=ctx,
            intent="create_transaction",
        )

    @server.tool(
        name="add_transactions",
        title="Record several expenses in MITA",
        description=ADD_MANY_DESCRIPTION,
        annotations=write_annotations(
            "Record several expenses in MITA", destructive=False, idempotent=True
        ),
        meta=tool_meta(
            FINANCE_WRITE, "Recording your expenses…", "Recorded your expenses"
        ),
    )
    async def add_transactions(
        ctx: Context,
        expenses: Annotated[
            List[ExpenseItem],
            Field(
                min_length=1,
                max_length=MAX_BATCH,
                description="The expenses, one item each, exactly as stated.",
            ),
        ],
        idempotency_key: IdempotencyKey,
        entry_method: EntryMethod = "conversation",
    ) -> Annotated[CallToolResult, TransactionsRecordedOut]:
        async def body(session, user_ctx, call):
            return await _record(
                session,
                user_ctx,
                call,
                expenses,
                idempotency_key,
                entry_method,
                "add_transactions",
            )

        return await runtime.execute_write(
            "add_transactions",
            FINANCE_WRITE,
            body,
            ctx=ctx,
            intent="create_batch",
        )

    @server.tool(
        name="update_transaction",
        title="Correct a MITA expense",
        description=UPDATE_DESCRIPTION,
        annotations=write_annotations(
            "Correct a MITA expense", destructive=True, idempotent=True
        ),
        meta=tool_meta(
            FINANCE_WRITE, "Correcting the expense…", "Corrected the expense"
        ),
    )
    async def update_transaction(
        ctx: Context,
        ref: Ref,
        amount: Optional[TransactionAmount] = None,
        category: Annotated[
            Optional[ExpenseCategory], Field(description=CATEGORY_HELP)
        ] = None,
        date: ExpenseDate = None,
        merchant: Annotated[
            Optional[str],
            Field(
                max_length=200,
                description="New merchant exactly as the user named it; an empty string removes it.",
            ),
        ] = None,
    ) -> Annotated[CallToolResult, TransactionChangeOut]:
        async def body(session, user_ctx, call):
            if (
                amount is None
                and category is None
                and date is None
                and merchant is None
            ):
                raise ValidationError(
                    "Send at least one field to change: amount, category, date or merchant."
                )

            def write(s) -> TransactionChangeOut:
                txn_id, row = writes.resolve_ref(s, user_ctx, keys, ref)
                if row is None:
                    raise ValidationError(
                        "This expense was deleted; it can no longer be changed."
                    )
                before = _recorded(keys, user_ctx, row)
                writes.apply_update(
                    s,
                    user_ctx,
                    txn_id,
                    amount=amount,
                    category=category,
                    day=date,
                    merchant=merchant,
                    merchant_sent=merchant is not None,
                )
                s.refresh(row)  # the committed row, not the updater's local-time copy
                after = _recorded(keys, user_ctx, row)
                changed = [
                    name
                    for name in ("amount", "category", "date", "merchant")
                    if getattr(before, name) != getattr(after, name)
                ]
                if changed:
                    analytics.emit("transaction_updated", fields=changed)
                return TransactionChangeOut(
                    status="updated" if changed else "unchanged",
                    changed_fields=changed,
                    transaction=after,
                    month_to_date_spent=money(writes.month_to_date_spent(s, user_ctx)),
                    notes=[],
                )

            return await session.run_sync(write)

        return await runtime.execute_write(
            "update_transaction",
            FINANCE_WRITE,
            body,
            ctx=ctx,
            intent="edit_transaction",
        )

    @server.tool(
        name="delete_transaction",
        title="Delete a MITA expense",
        description=DELETE_DESCRIPTION,
        annotations=write_annotations(
            "Delete a MITA expense", destructive=True, idempotent=True
        ),
        meta=tool_meta(FINANCE_WRITE, "Deleting the expense…", "Deleted the expense"),
    )
    async def delete_transaction(
        ctx: Context, ref: Ref
    ) -> Annotated[CallToolResult, TransactionChangeOut]:
        async def body(session, user_ctx, call):
            def write(s) -> TransactionChangeOut:
                txn_id, row = writes.resolve_ref(s, user_ctx, keys, ref)
                if row is None:
                    deleted_row = writes.load_owned(
                        s, user_ctx, [txn_id], include_deleted=True
                    )[0]
                    return TransactionChangeOut(
                        status="already_deleted",
                        changed_fields=[],
                        transaction=_recorded(keys, user_ctx, deleted_row),
                        month_to_date_spent=money(
                            writes.month_to_date_spent(s, user_ctx)
                        ),
                        notes=["This expense was already deleted; nothing changed."],
                    )
                snapshot = _recorded(keys, user_ctx, row)
                writes.apply_delete(s, user_ctx, txn_id)
                analytics.emit("transaction_deleted")
                return TransactionChangeOut(
                    status="deleted",
                    changed_fields=[],
                    transaction=snapshot,
                    month_to_date_spent=money(writes.month_to_date_spent(s, user_ctx)),
                    notes=[],
                )

            return await session.run_sync(write)

        return await runtime.execute_write(
            "delete_transaction",
            FINANCE_WRITE,
            body,
            ctx=ctx,
            intent="delete_transaction",
        )
