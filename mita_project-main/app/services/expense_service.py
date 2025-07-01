from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime

from app.schemas.expense import ExpenseEntry, ExpenseOut
from app.db.models.expense import Expense


async def add_user_expense(entry: ExpenseEntry, db: AsyncSession) -> ExpenseOut:
    expense = Expense(
        user_id=entry.user_id,
        action=entry.action,
        amount=entry.amount,
        date=datetime.strptime(entry.date, "%Y-%m-%d").date()
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return ExpenseOut(
        user_id=expense.user_id,
        action=expense.action,
        amount=expense.amount,
        date=expense.date
    )


async def get_user_expense_history(user_id: str, db: AsyncSession) -> List[ExpenseOut]:
    result = await db.execute(select(Expense).where(Expense.user_id == user_id))
    expenses = result.scalars().all()
    return [
        ExpenseOut(
            user_id=expense.user_id,
            action=expense.action,
            amount=expense.amount,
            date=expense.date
        ) for expense in expenses
    ]
