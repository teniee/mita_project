"""
MODULE 5: Goal-Transaction Integration Service

Automatically updates goal progress when transactions are created.
Links spending/savings to financial goals.
"""

from typing import Optional
from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session

from app.db.models import Goal, Transaction
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class GoalTransactionService:
    """Service for handling goal-transaction integration"""

    @staticmethod
    def process_transaction_for_goal(
        db: Session,
        transaction: Transaction,
        goal_id: Optional[UUID] = None
    ) -> Optional[Goal]:
        """
        Process a transaction and update the associated goal's progress.

        Args:
            db: Database session
            transaction: The transaction to process
            goal_id: Optional goal_id (if not set on transaction)

        Returns:
            Updated Goal if processed, None otherwise
        """
        try:
            # Determine which goal to update
            target_goal_id = goal_id or transaction.goal_id
            if not target_goal_id:
                logger.debug(f"Transaction {transaction.id} has no goal_id, skipping")
                return None

            # Get the goal
            goal = db.query(Goal).filter(
                Goal.id == target_goal_id,
                Goal.user_id == transaction.user_id
            ).first()

            if not goal:
                logger.warning(f"Goal {target_goal_id} not found for transaction {transaction.id}")
                return None

            # Only update active goals
            if goal.status != 'active':
                logger.info(f"Goal {goal.id} is {goal.status}, not updating from transaction")
                return None

            # Add the transaction amount to savings
            # Note: For income/savings transactions, amount is positive
            # For expenses toward a goal (like buying something for the goal), amount might be negative
            amount_to_add = abs(Decimal(str(transaction.amount)))

            logger.info(
                f"Adding ${amount_to_add} from transaction {transaction.id} to goal '{goal.title}' "
                f"(current: ${goal.saved_amount}, target: ${goal.target_amount})"
            )

            # Use the model's add_savings method which handles progress calculation
            goal.add_savings(amount_to_add)

            db.commit()
            db.refresh(goal)

            logger.info(
                f"Goal '{goal.title}' updated: progress={goal.progress}%, "
                f"saved=${goal.saved_amount}, status={goal.status}"
            )

            return goal

        except Exception as e:
            logger.error(f"Error processing transaction for goal: {e}", exc_info=True)
            db.rollback()
            return None

    @staticmethod
    def link_transaction_to_goal(
        db: Session,
        transaction_id: UUID,
        goal_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Link an existing transaction to a goal and update progress.

        Args:
            db: Database session
            transaction_id: Transaction to link
            goal_id: Goal to link to
            user_id: User ID for security check

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get transaction
            transaction = db.query(Transaction).filter(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id
            ).first()

            if not transaction:
                logger.warning(f"Transaction {transaction_id} not found")
                return False

            # Verify goal belongs to user
            goal = db.query(Goal).filter(
                Goal.id == goal_id,
                Goal.user_id == user_id
            ).first()

            if not goal:
                logger.warning(f"Goal {goal_id} not found for user {user_id}")
                return False

            # Link and process
            transaction.goal_id = goal_id
            db.commit()

            # Update goal progress
            result = GoalTransactionService.process_transaction_for_goal(
                db, transaction, goal_id
            )

            return result is not None

        except Exception as e:
            logger.error(f"Error linking transaction to goal: {e}", exc_info=True)
            db.rollback()
            return False

    @staticmethod
    def unlink_transaction_from_goal(
        db: Session,
        transaction_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Remove transaction-goal link and recalculate goal progress.

        Args:
            db: Database session
            transaction_id: Transaction to unlink
            user_id: User ID for security check

        Returns:
            True if successful, False otherwise
        """
        try:
            transaction = db.query(Transaction).filter(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id
            ).first()

            if not transaction or not transaction.goal_id:
                return False

            goal_id = transaction.goal_id
            amount = abs(Decimal(str(transaction.amount)))

            # Unlink
            transaction.goal_id = None
            db.commit()

            # Recalculate goal progress by subtracting the amount
            goal = db.query(Goal).filter(Goal.id == goal_id).first()
            if goal:
                goal.saved_amount = max(Decimal('0'), goal.saved_amount - amount)
                goal.update_progress()
                db.commit()

                logger.info(f"Unlinked transaction {transaction_id} from goal {goal_id}, recalculated progress")

            return True

        except Exception as e:
            logger.error(f"Error unlinking transaction from goal: {e}", exc_info=True)
            db.rollback()
            return False

    @staticmethod
    def get_goal_transactions(
        db: Session,
        goal_id: UUID,
        user_id: UUID
    ) -> list[Transaction]:
        """
        Get all transactions linked to a specific goal.

        Args:
            db: Database session
            goal_id: Goal ID
            user_id: User ID for security

        Returns:
            List of transactions
        """
        try:
            transactions = db.query(Transaction).filter(
                Transaction.goal_id == goal_id,
                Transaction.user_id == user_id
            ).order_by(Transaction.spent_at.desc()).all()

            return transactions

        except Exception as e:
            logger.error(f"Error getting goal transactions: {e}", exc_info=True)
            return []

    @staticmethod
    def calculate_goal_progress_from_transactions(
        db: Session,
        goal_id: UUID,
        user_id: UUID
    ) -> Decimal:
        """
        Calculate total saved amount from all linked transactions.

        Args:
            db: Database session
            goal_id: Goal ID
            user_id: User ID for security

        Returns:
            Total amount from transactions
        """
        try:
            from sqlalchemy import func

            total = db.query(
                func.sum(Transaction.amount)
            ).filter(
                Transaction.goal_id == goal_id,
                Transaction.user_id == user_id
            ).scalar() or Decimal('0')

            return abs(Decimal(str(total)))

        except Exception as e:
            logger.error(f"Error calculating goal progress from transactions: {e}", exc_info=True)
            return Decimal('0')


# Singleton instance
_goal_transaction_service: Optional[GoalTransactionService] = None


def get_goal_transaction_service() -> GoalTransactionService:
    """Get singleton goal transaction service instance"""
    global _goal_transaction_service
    if _goal_transaction_service is None:
        _goal_transaction_service = GoalTransactionService()
    return _goal_transaction_service
