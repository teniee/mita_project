"""
MODULE 5: Budgeting Goals - Comprehensive Tests
Tests for Goal model, API endpoints, and business logic
"""
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import uuid4

from app.db.models import Goal


class TestGoalModel:
    """Test Goal model methods and properties"""

    def test_goal_creation(self):
        """Test basic goal creation"""
        goal = Goal(
            id=uuid4(),
            user_id=uuid4(),
            title="Emergency Fund",
            description="Build a 6-month emergency fund",
            category="Emergency",
            target_amount=Decimal('5000.00'),
            saved_amount=Decimal('1000.00'),
            status='active',
            priority='high',
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

        assert goal.title == "Emergency Fund"
        assert goal.category == "Emergency"
        assert goal.target_amount == Decimal('5000.00')
        assert goal.saved_amount == Decimal('1000.00')
        assert goal.status == 'active'

    def test_goal_progress_calculation(self):
        """Test progress calculation"""
        goal = Goal(
            id=uuid4(),
            user_id=uuid4(),
            title="Test Goal",
            target_amount=Decimal('1000.00'),
            saved_amount=Decimal('250.00'),
            status='active',
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

        goal.update_progress()

        assert goal.progress == Decimal('25.00')

    def test_goal_auto_completion(self):
        """Test that goal auto-completes when progress reaches 100%"""
        goal = Goal(
            id=uuid4(),
            user_id=uuid4(),
            title="Test Goal",
            target_amount=Decimal('1000.00'),
            saved_amount=Decimal('1000.00'),
            status='active',
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

        goal.update_progress()

        assert goal.progress == Decimal('100.00')
        assert goal.status == 'completed'
        assert goal.completed_at is not None

    def test_goal_add_savings(self):
        """Test adding savings to a goal"""
        goal = Goal(
            id=uuid4(),
            user_id=uuid4(),
            title="Test Goal",
            target_amount=Decimal('1000.00'),
            saved_amount=Decimal('200.00'),
            status='active',
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

        goal.add_savings(Decimal('300.00'))

        assert goal.saved_amount == Decimal('500.00')
        assert goal.progress == Decimal('50.00')

    def test_goal_remaining_amount(self):
        """Test remaining amount calculation"""
        goal = Goal(
            id=uuid4(),
            user_id=uuid4(),
            title="Test Goal",
            target_amount=Decimal('1000.00'),
            saved_amount=Decimal('300.00'),
            status='active',
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

        assert goal.remaining_amount == Decimal('700.00')

    def test_goal_is_overdue(self):
        """Test overdue detection"""
        # Goal with past target date
        past_goal = Goal(
            id=uuid4(),
            user_id=uuid4(),
            title="Past Goal",
            target_amount=Decimal('1000.00'),
            saved_amount=Decimal('500.00'),
            status='active',
            target_date=date.today() - timedelta(days=1),
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

        assert past_goal.is_overdue == True

        # Goal with future target date
        future_goal = Goal(
            id=uuid4(),
            user_id=uuid4(),
            title="Future Goal",
            target_amount=Decimal('1000.00'),
            saved_amount=Decimal('500.00'),
            status='active',
            target_date=date.today() + timedelta(days=30),
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

        assert future_goal.is_overdue == False

    def test_goal_is_completed(self):
        """Test completion detection"""
        completed_goal = Goal(
            id=uuid4(),
            user_id=uuid4(),
            title="Completed Goal",
            target_amount=Decimal('1000.00'),
            saved_amount=Decimal('1000.00'),
            status='completed',
            progress=Decimal('100.00'),
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

        assert completed_goal.is_completed == True

        active_goal = Goal(
            id=uuid4(),
            user_id=uuid4(),
            title="Active Goal",
            target_amount=Decimal('1000.00'),
            saved_amount=Decimal('500.00'),
            status='active',
            progress=Decimal('50.00'),
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

        assert active_goal.is_completed == False


@pytest.mark.parametrize("saved,target,expected_progress", [
    (0, 1000, 0),
    (250, 1000, 25),
    (500, 1000, 50),
    (750, 1000, 75),
    (1000, 1000, 100),
    (1200, 1000, 100),  # Should cap at 100
])
def test_goal_progress_various_amounts(saved, target, expected_progress):
    """Test progress calculation with various amounts"""
    goal = Goal(
        id=uuid4(),
        user_id=uuid4(),
        title="Test Goal",
        target_amount=Decimal(str(target)),
        saved_amount=Decimal(str(saved)),
        status='active',
        created_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )

    goal.update_progress()

    assert float(goal.progress) == expected_progress


def test_goal_categories():
    """Test that all category types are supported"""
    categories = ['Savings', 'Travel', 'Emergency', 'Technology', 'Education',
                 'Health', 'Home', 'Vehicle', 'Investment', 'Other']

    for category in categories:
        goal = Goal(
            id=uuid4(),
            user_id=uuid4(),
            title=f"{category} Goal",
            category=category,
            target_amount=Decimal('1000.00'),
            saved_amount=Decimal('0.00'),
            status='active',
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

        assert goal.category == category


def test_goal_statuses():
    """Test that all status types are supported"""
    statuses = ['active', 'completed', 'paused', 'cancelled']

    for status in statuses:
        goal = Goal(
            id=uuid4(),
            user_id=uuid4(),
            title="Test Goal",
            target_amount=Decimal('1000.00'),
            saved_amount=Decimal('0.00'),
            status=status,
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

        assert goal.status == status


def test_goal_priorities():
    """Test that all priority levels are supported"""
    priorities = ['high', 'medium', 'low']

    for priority in priorities:
        goal = Goal(
            id=uuid4(),
            user_id=uuid4(),
            title="Test Goal",
            target_amount=Decimal('1000.00'),
            saved_amount=Decimal('0.00'),
            status='active',
            priority=priority,
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

        assert goal.priority == priority
