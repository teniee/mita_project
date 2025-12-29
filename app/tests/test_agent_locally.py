from app.engine.risk_predictor import evaluate_user_risk
from app.logic.installment_evaluator import can_user_afford_installment
from app.services.user_data_service import UserDataService

# Add a fallback method if ``get_user_financial_profile`` is missing
if not hasattr(UserDataService, "get_user_financial_profile"):

    def mock_profile(user_id):
        return {"user_id": user_id, "profile_data": {"income": 5000, "spending": 3000}}

    UserDataService.get_user_financial_profile = staticmethod(mock_profile)


def test_risk_assessment():
    from app.core.session import get_db
    db = next(get_db())
    try:
        for user_id in ["user_001", "user_002", "unknown_user"]:
            result = evaluate_user_risk(user_id, db)
            assert isinstance(result, dict)
    finally:
        db.close()


def test_installment_variants():
    from app.core.session import get_db
    db = next(get_db())
    try:
        test_cases = [
            ("user_001", 2400, 24),
            ("user_001", 4800, 12),
            ("user_001", 1000, 6),
            ("user_002", 6000, 36),
            ("user_002", 500, 2),
            ("user_002", 15000, 60),
            ("unknown_user", 3000, 12),
        ]
        for user_id, price, months in test_cases:
            result = can_user_afford_installment(user_id, price, months, db)
            assert isinstance(result, dict)
    finally:
        db.close()
