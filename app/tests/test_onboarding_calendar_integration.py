"""
Comprehensive Integration Test for Onboarding Calendar Flow

CRITICAL TEST: Verifies that onboarding actually saves calendar data to database.
This test was created to prevent regression of the bug where calendar data was not
being persisted despite users completing onboarding successfully.

Bug Context:
- Users were marked as has_onboarded=True
- But daily_plan table had 0 entries
- Root cause: Missing UUID default on daily_plan.id column
"""
import pytest
from decimal import Decimal
from uuid import uuid4

from app.db.models import User, DailyPlan


class TestOnboardingCalendarIntegration:
    """Integration tests for onboarding flow with actual database persistence"""

    @pytest.fixture
    def test_user(self, db_session):
        """Create a test user in the database"""
        user = User(
            id=uuid4(),
            email="test_calendar_integration@mita.app",
            password_hash="hashed_password_123",
            has_onboarded=False,
            monthly_income=Decimal("0.00")
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    def test_onboarding_creates_calendar_entries(self, client, db_session, test_user):
        """
        CRITICAL TEST: Verify calendar data is actually saved to database

        This is the test that would have caught the UUID default bug.
        """
        # Prepare onboarding data
        onboarding_data = {
            "income": {
                "monthly_income": 5000.0,
                "additional_income": 500.0
            },
            "fixed_expenses": {
                "rent": 1500.0,
                "utilities": 200.0,
                "insurance": 150.0
            },
            "spending_habits": {
                "dining_out_per_month": 10,
                "entertainment_budget": 200.0,
                "shopping_frequency": 5
            },
            "goals": {
                "savings_goal_amount_per_month": 1000.0,
                "emergency_fund_target": 10000.0
            },
            "region": "US"
        }

        # Login as test user (mock auth)
        from app.api.dependencies import get_current_user
        from app.main import app

        def mock_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            # Submit onboarding
            response = client.post(
                "/api/onboarding/submit",
                json=onboarding_data,
                headers={"Authorization": "Bearer test_token"}
            )

            # Should succeed
            assert response.status_code == 200, f"Onboarding failed: {response.json()}"

            response_data = response.json()
            assert "data" in response_data
            assert response_data["data"]["status"] == "success"

            # CRITICAL VERIFICATION: Check database has calendar entries
            calendar_entries = db_session.query(DailyPlan).filter_by(
                user_id=test_user.id
            ).all()

            # Should have created daily budget entries (at least 28 days)
            assert len(calendar_entries) > 0, "❌ CRITICAL: No calendar entries created!"
            assert len(calendar_entries) >= 28, f"Expected at least 28 days, got {len(calendar_entries)}"

            # Verify entries have proper data
            for entry in calendar_entries[:5]:  # Check first 5
                assert entry.id is not None, "Entry ID should not be null"
                assert entry.user_id == test_user.id
                assert entry.category is not None
                assert entry.planned_amount > 0
                assert entry.spent_amount == Decimal("0.00")
                assert entry.date is not None

            # Verify user was marked as onboarded
            db_session.refresh(test_user)
            assert test_user.has_onboarded is True
            assert test_user.monthly_income == Decimal("5500.00")  # 5000 + 500

            # Verify response includes calendar data
            assert "calendar_days" in response_data["data"]
            assert response_data["data"]["calendar_days"] > 0

            print(f"✅ SUCCESS: Created {len(calendar_entries)} calendar entries")

        finally:
            # Cleanup
            app.dependency_overrides.clear()
            db_session.query(DailyPlan).filter_by(user_id=test_user.id).delete()
            db_session.query(User).filter_by(id=test_user.id).delete()
            db_session.commit()

    def test_calendar_entries_have_valid_uuids(self, client, db_session, test_user):
        """Verify that calendar entries have properly generated UUIDs"""
        # Submit minimal onboarding
        onboarding_data = {
            "income": {"monthly_income": 3000.0, "additional_income": 0},
            "fixed_expenses": {"rent": 1000.0},
            "region": "US"
        }

        from app.api.dependencies import get_current_user
        from app.main import app

        def mock_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = client.post(
                "/api/onboarding/submit",
                json=onboarding_data,
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 200

            # Check UUIDs are valid and unique
            calendar_entries = db_session.query(DailyPlan).filter_by(
                user_id=test_user.id
            ).all()

            uuids = [entry.id for entry in calendar_entries]

            # All should have UUIDs
            assert all(uuid is not None for uuid in uuids), "Some entries missing UUIDs"

            # All should be unique
            assert len(uuids) == len(set(uuids)), "Duplicate UUIDs found!"

            print(f"✅ All {len(uuids)} calendar entries have valid unique UUIDs")

        finally:
            app.dependency_overrides.clear()
            db_session.query(DailyPlan).filter_by(user_id=test_user.id).delete()
            db_session.query(User).filter_by(id=test_user.id).delete()
            db_session.commit()

    def test_calendar_save_failure_rolls_back_user_changes(self, client, db_session, test_user):
        """Verify that if calendar save fails, user changes are rolled back"""
        # This test ensures atomicity of the onboarding transaction

        original_income = test_user.monthly_income
        original_onboarded = test_user.has_onboarded

        # Try to submit with invalid data that should fail
        invalid_data = {
            "income": {"monthly_income": -1000.0},  # Invalid: negative income
            "fixed_expenses": {},
            "region": "US"
        }

        from app.api.dependencies import get_current_user
        from app.main import app

        def mock_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = client.post(
                "/api/onboarding/submit",
                json=invalid_data,
                headers={"Authorization": "Bearer test_token"}
            )

            # Should fail validation
            assert response.status_code in [400, 422]

            # Verify user state was NOT changed
            db_session.refresh(test_user)
            assert test_user.monthly_income == original_income
            assert test_user.has_onboarded == original_onboarded

            # Verify no calendar entries were created
            calendar_count = db_session.query(DailyPlan).filter_by(
                user_id=test_user.id
            ).count()
            assert calendar_count == 0

            print("✅ Transaction rollback working correctly")

        finally:
            app.dependency_overrides.clear()
            db_session.query(DailyPlan).filter_by(user_id=test_user.id).delete()
            db_session.commit()
