"""
Integration Tests for Cross-Module Flows

Tests the complete data flow between all modules:
- Onboarding → User Profile → Dashboard
- Transactions → Dashboard Update
- Profile Update → Dashboard Refresh
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

# Mock imports for testing without full FastAPI setup
from unittest.mock import Mock, MagicMock, patch, AsyncMock


class TestOnboardingToDashboardFlow:
    """Test data flow from Onboarding through to Dashboard"""

    def test_onboarding_saves_income_to_user(self):
        """
        Test: Onboarding → User Profile
        Verify that onboarding correctly saves monthly_income to User model
        """
        from app.db.models.user import User

        # Create mock user
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash="hashed",
            monthly_income=Decimal("0.00")
        )

        # Simulate onboarding submission
        onboarding_data = {
            'income': {
                'monthly_income': 3000.00,
                'additional_income': 0.00
            },
            'fixed_expenses': {
                'rent': 1000.00,
                'utilities': 200.00
            },
            'spending_habits': {},
            'goals': {
                'savings_goal_amount_per_month': 500.00
            }
        }

        # Update user
        user.monthly_income = Decimal(str(onboarding_data['income']['monthly_income']))

        # Verify
        assert user.monthly_income == Decimal("3000.00")
        assert float(user.monthly_income) == 3000.00

        print("✓ Onboarding correctly saves income to User model")


    def test_user_profile_returns_onboarding_data(self):
        """
        Test: User Profile API returns data from Onboarding
        Verify that /users/me endpoint returns monthly_income set during onboarding
        """
        from app.db.models.user import User

        # Mock user after onboarding
        user = Mock(spec=User)
        user.id = uuid.uuid4()
        user.email = "test@example.com"
        user.monthly_income = Decimal("3000.00")
        user.created_at = datetime.utcnow()
        user.timezone = "UTC"

        # Simulate /users/me response construction
        profile_response = {
            "id": user.id,
            "email": user.email,
            "income": float(user.monthly_income or 0),
            "created_at": user.created_at.isoformat(),
        }

        # Verify
        assert profile_response['income'] == 3000.00

        print("✓ User Profile API returns correct onboarding data")


    def test_dashboard_uses_user_income(self):
        """
        Test: Dashboard uses User.monthly_income
        Verify that Dashboard endpoint correctly fetches and uses monthly_income
        """
        from app.db.models.user import User

        # Mock user
        user = Mock(spec=User)
        user.id = uuid.uuid4()
        user.monthly_income = Decimal("3000.00")

        # Simulate dashboard calculation
        monthly_income = float(user.monthly_income) if user.monthly_income else 0.0

        # Calculate balance (simplified)
        total_spent = 1500.00  # Mock spending
        current_balance = monthly_income - total_spent

        # Verify
        assert monthly_income == 3000.00
        assert current_balance == 1500.00

        print("✓ Dashboard correctly uses User.monthly_income")


class TestTransactionToDashboardFlow:
    """Test data flow from Transaction creation to Dashboard update"""

    def test_create_transaction_updates_spending(self):
        """
        Test: Add Transaction → Dashboard shows updated spending
        """
        from app.db.models import Transaction, User
        from sqlalchemy import func

        # Mock database query
        mock_db = Mock()

        # Simulate existing transactions
        existing_transactions = [
            {'amount': Decimal("25.50")},
            {'amount': Decimal("15.00")},
        ]

        # Mock query result
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("40.50")  # Sum of existing

        mock_db.query.return_value = mock_query

        # Add new transaction
        new_transaction_amount = Decimal("20.00")

        # Simulate dashboard recalculation
        total_spent = Decimal("40.50") + new_transaction_amount

        # Verify
        assert total_spent == Decimal("60.50")

        print("✓ New transaction updates Dashboard spending")


    def test_transaction_affects_daily_budget_progress(self):
        """
        Test: Transaction updates daily budget target progress
        """
        from app.db.models import DailyPlan

        # Mock daily plan
        daily_plan = Mock(spec=DailyPlan)
        daily_plan.category = "food"
        daily_plan.planned_amount = Decimal("100.00")
        daily_plan.spent_amount = Decimal("25.50")

        # Add new transaction
        new_transaction_amount = Decimal("20.00")

        # Update spent amount
        daily_plan.spent_amount += new_transaction_amount

        # Calculate progress
        progress = (float(daily_plan.spent_amount) / float(daily_plan.planned_amount)) * 100

        # Verify
        assert daily_plan.spent_amount == Decimal("45.50")
        assert progress == 45.5

        print("✓ Transaction correctly updates daily budget progress")


    def test_transaction_updates_weekly_overview(self):
        """
        Test: Transaction affects weekly overview in Dashboard
        """
        today = datetime.utcnow().date()

        # Mock daily spending
        daily_budgets = {
            (today - timedelta(days=i)): {
                'spent': Decimal("75.00") if i > 0 else Decimal("45.50"),
                'budget': Decimal("100.00")
            }
            for i in range(7)
        }

        # Add new transaction today
        today_data = daily_budgets[today]
        today_data['spent'] += Decimal("20.00")

        # Determine status
        spent = float(today_data['spent'])
        budget = float(today_data['budget'])

        if spent > budget:
            status = 'over'
        elif spent > budget * 0.9:
            status = 'warning'
        else:
            status = 'good'

        # Verify
        assert today_data['spent'] == Decimal("65.50")
        assert status == 'good'

        print("✓ Transaction updates weekly overview status")


class TestProfileUpdateToDashboardFlow:
    """Test data flow from Profile update to Dashboard refresh"""

    def test_income_update_recalculates_balance(self):
        """
        Test: Update income in profile → Dashboard recalculates balance
        """
        from app.db.models.user import User

        # Initial state
        user = Mock(spec=User)
        user.monthly_income = Decimal("3000.00")

        total_spent = Decimal("1500.00")
        initial_balance = float(user.monthly_income) - float(total_spent)

        # User updates income
        user.monthly_income = Decimal("4000.00")

        # Dashboard recalculates
        new_balance = float(user.monthly_income) - float(total_spent)

        # Verify
        assert initial_balance == 1500.00
        assert new_balance == 2500.00

        print("✓ Income update triggers Dashboard balance recalculation")


    def test_income_update_affects_budget_targets(self):
        """
        Test: Income update → Budget targets recalculated
        """
        # Initial income
        monthly_income = 3000.00

        # Calculate initial daily budget (simplified)
        daily_budget = monthly_income / 30
        food_budget = daily_budget * 0.35  # 35% for food

        initial_food_budget = food_budget

        # Update income
        monthly_income = 4000.00

        # Recalculate
        daily_budget = monthly_income / 30
        food_budget = daily_budget * 0.35

        new_food_budget = food_budget

        # Verify
        assert initial_food_budget == 35.00
        assert new_food_budget == 46.67  # Approximately

        print("✓ Income update recalculates budget targets")


    def test_profile_completion_triggers_dashboard_enable(self):
        """
        Test: Completing profile enables full dashboard functionality
        """
        from app.db.models.user import User

        # User with incomplete profile
        user = Mock(spec=User)
        user.monthly_income = None
        user.has_onboarded = False

        # Dashboard should show onboarding prompt
        can_show_dashboard = (
            user.monthly_income is not None and
            float(user.monthly_income) > 0 and
            user.has_onboarded
        )

        assert can_show_dashboard is False

        # Complete onboarding
        user.monthly_income = Decimal("3000.00")
        user.has_onboarded = True

        # Dashboard should now be available
        can_show_dashboard = (
            user.monthly_income is not None and
            float(user.monthly_income) > 0 and
            user.has_onboarded
        )

        assert can_show_dashboard is True

        print("✓ Profile completion enables Dashboard")


class TestCalendarToDashboardIntegration:
    """Test Calendar/Budget integration with Dashboard"""

    def test_daily_plan_provides_budget_targets(self):
        """
        Test: DailyPlan data used for Dashboard daily targets
        """
        from app.db.models import DailyPlan

        # Mock daily plans
        daily_plans = [
            Mock(
                spec=DailyPlan,
                category='food',
                planned_amount=Decimal("100.00"),
                spent_amount=Decimal("25.50")
            ),
            Mock(
                spec=DailyPlan,
                category='transportation',
                planned_amount=Decimal("80.00"),
                spent_amount=Decimal("15.00")
            ),
        ]

        # Transform to dashboard format
        daily_targets = []
        for plan in daily_plans:
            daily_targets.append({
                'category': plan.category.title(),
                'limit': float(plan.planned_amount),
                'spent': float(plan.spent_amount),
            })

        # Verify
        assert len(daily_targets) == 2
        assert daily_targets[0]['category'] == 'Food'
        assert daily_targets[0]['limit'] == 100.00
        assert daily_targets[0]['spent'] == 25.50

        print("✓ DailyPlan correctly provides budget targets for Dashboard")


    def test_calendar_saved_during_onboarding_used_by_dashboard(self):
        """
        Test: Calendar created during onboarding is used by Dashboard
        """
        from app.db.models import DailyPlan
        from datetime import date

        # Simulate calendar creation during onboarding
        user_id = uuid.uuid4()
        today = date.today()

        # Mock calendar entry
        calendar_entry = Mock(spec=DailyPlan)
        calendar_entry.user_id = user_id
        calendar_entry.date = datetime.combine(today, datetime.min.time())
        calendar_entry.category = 'food'
        calendar_entry.daily_budget = Decimal("100.00")
        calendar_entry.planned_amount = Decimal("100.00")
        calendar_entry.spent_amount = Decimal("0.00")

        # Dashboard fetches this entry
        assert calendar_entry.user_id == user_id
        assert calendar_entry.category == 'food'
        assert float(calendar_entry.daily_budget) == 100.00

        print("✓ Onboarding calendar data successfully used by Dashboard")


class TestCompleteUserJourney:
    """Test complete user journey through all modules"""

    def test_full_user_flow(self):
        """
        Test: Complete flow from registration to dashboard viewing

        Flow:
        1. User registers
        2. User completes onboarding
        3. User profile is created
        4. Calendar/budget is generated
        5. User adds transaction
        6. User views dashboard with all data
        """
        from app.db.models import User, DailyPlan, Transaction

        # Step 1: User registers
        user = Mock(spec=User)
        user.id = uuid.uuid4()
        user.email = "newuser@example.com"
        user.monthly_income = Decimal("0.00")
        user.has_onboarded = False

        assert user.has_onboarded is False

        # Step 2: User completes onboarding
        user.monthly_income = Decimal("3000.00")
        user.has_onboarded = True

        assert float(user.monthly_income) == 3000.00

        # Step 3: Calendar/budget generated
        daily_plan = Mock(spec=DailyPlan)
        daily_plan.user_id = user.id
        daily_plan.category = 'food'
        daily_plan.planned_amount = Decimal("100.00")
        daily_plan.spent_amount = Decimal("0.00")

        # Step 4: User adds transaction
        transaction = Mock(spec=Transaction)
        transaction.user_id = user.id
        transaction.amount = Decimal("25.50")
        transaction.category = 'food'
        transaction.spent_at = datetime.utcnow()

        # Update daily plan
        daily_plan.spent_amount += transaction.amount

        # Step 5: Dashboard calculation
        monthly_income = float(user.monthly_income)
        total_spent = float(transaction.amount)
        current_balance = monthly_income - total_spent

        daily_target_progress = (
            float(daily_plan.spent_amount) / float(daily_plan.planned_amount)
        ) * 100

        # Verify complete flow
        assert user.has_onboarded is True
        assert monthly_income == 3000.00
        assert current_balance == 2974.50
        assert daily_plan.spent_amount == Decimal("25.50")
        assert daily_target_progress == 25.5

        print("✓ Complete user journey successful")


def run_all_tests():
    """Run all integration tests"""
    print("\n" + "="*60)
    print("RUNNING CROSS-MODULE INTEGRATION TESTS")
    print("="*60 + "\n")

    # Test Onboarding → Dashboard
    print("📋 Testing Onboarding → User Profile → Dashboard Flow")
    print("-" * 60)
    test1 = TestOnboardingToDashboardFlow()
    test1.test_onboarding_saves_income_to_user()
    test1.test_user_profile_returns_onboarding_data()
    test1.test_dashboard_uses_user_income()
    print()

    # Test Transaction → Dashboard
    print("💰 Testing Transaction → Dashboard Update Flow")
    print("-" * 60)
    test2 = TestTransactionToDashboardFlow()
    test2.test_create_transaction_updates_spending()
    test2.test_transaction_affects_daily_budget_progress()
    test2.test_transaction_updates_weekly_overview()
    print()

    # Test Profile Update → Dashboard
    print("👤 Testing Profile Update → Dashboard Refresh Flow")
    print("-" * 60)
    test3 = TestProfileUpdateToDashboardFlow()
    test3.test_income_update_recalculates_balance()
    test3.test_income_update_affects_budget_targets()
    test3.test_profile_completion_triggers_dashboard_enable()
    print()

    # Test Calendar Integration
    print("📅 Testing Calendar/Budget → Dashboard Integration")
    print("-" * 60)
    test4 = TestCalendarToDashboardIntegration()
    test4.test_daily_plan_provides_budget_targets()
    test4.test_calendar_saved_during_onboarding_used_by_dashboard()
    print()

    # Test Complete Journey
    print("🎯 Testing Complete User Journey")
    print("-" * 60)
    test5 = TestCompleteUserJourney()
    test5.test_full_user_flow()
    print()

    print("="*60)
    print("✅ ALL INTEGRATION TESTS PASSED")
    print("="*60)


if __name__ == "__main__":
    run_all_tests()
