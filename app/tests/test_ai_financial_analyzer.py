"""
Comprehensive tests for AIFinancialAnalyzer ML-based financial analysis.

Tests the core ML algorithms for pattern detection, anomaly detection,
health scoring, and savings optimization WITHOUT GPT-4 calls.

Coverage includes:
- Spending pattern detection (weekend, impulse, subscriptions)
- Statistical anomaly detection (2σ outliers)
- Financial health scoring with dynamic thresholds
- Savings optimization algorithms
- Category concentration analysis (HHI)
- Monthly variance calculations
- Dynamic threshold adaptation by income
- Personalized feedback generation

Total: 25+ comprehensive test cases covering 1121 lines of AIFinancialAnalyzer
"""

import os
import sys
import types
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

# ============================================================================
# ENVIRONMENT SETUP (MUST come before app imports)
# ============================================================================

os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test_mita?sslmode=disable')
os.environ.setdefault('SECRET_KEY', 'test_secret_key_for_testing_only')
os.environ.setdefault('ENVIRONMENT', 'test')
os.environ.setdefault('FIREBASE_JSON', '{}')
os.environ.setdefault('OPENAI_API_KEY', 'sk-test-key')

# Mock Firebase
dummy = types.ModuleType("firebase_admin")
dummy._apps = []
dummy.credentials = types.SimpleNamespace(ApplicationDefault=lambda: None, Certificate=lambda *a, **k: None)
dummy.initialize_app = lambda cred=None: None
sys.modules["firebase_admin"] = dummy
sys.modules["firebase_admin.credentials"] = dummy.credentials

# ============================================================================
# APP IMPORTS (after env setup)
# ============================================================================

from app.services.ai_financial_analyzer import AIFinancialAnalyzer
from app.services.core.dynamic_threshold_service import UserContext

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_user():
    """Create a mock user with proper numeric attributes for UserContext"""
    user = Mock()
    user.id = "test_user_analyzer_123"
    user.monthly_income = 5000.0
    user.annual_income = 60000.0
    user.age = 35
    user.region = "US"
    user.family_size = 1
    user.debt_to_income_ratio = 0.0
    user.current_savings_rate = 0.0
    user.housing_status = "rent"
    user.life_stage = "single"
    return user

@pytest.fixture
def mock_db(mock_user):
    """Create mock database session that returns mock_user on User query"""
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = mock_user
    return db

@pytest.fixture
def test_user_id():
    """Test user ID"""
    return "test_user_analyzer_123"

@pytest.fixture
def low_income_user():
    """Low income user for threshold testing"""
    user = Mock()
    user.id = "low_income_user"
    user.monthly_income = 2000.0
    user.annual_income = 24000.0
    user.age = 25
    user.region = "US"
    user.family_size = 1
    user.housing_status = "rent"
    user.life_stage = "single"
    return user

@pytest.fixture
def high_income_user():
    """High income user for threshold testing"""
    user = Mock()
    user.id = "high_income_user"
    user.monthly_income = 15000.0
    user.annual_income = 180000.0
    user.age = 40
    user.region = "US"
    user.family_size = 4
    user.housing_status = "own"
    user.life_stage = "married_with_children"
    return user

@pytest.fixture
def sample_expenses_weekend_pattern():
    """Sample expenses showing weekend overspending pattern"""
    expenses = []
    base_date = datetime.utcnow() - timedelta(days=60)

    for day in range(60):
        current_date = base_date + timedelta(days=day)
        is_weekend = current_date.weekday() >= 5

        expense = Mock()
        expense.amount = Decimal('75.00') if is_weekend else Decimal('50.00')
        expense.category = 'food'
        expense.date = current_date
        expense.description = f"Food expense day {day}"
        expense.spent_at = current_date
        expense.created_at = current_date
        expenses.append(expense)

    return expenses

@pytest.fixture
def sample_expenses_small_purchases():
    """Sample expenses with many small frequent purchases"""
    expenses = []
    base_date = datetime.utcnow() - timedelta(days=30)

    for day in range(30):
        # 3 small purchases per day
        for purchase in range(3):
            expense = Mock()
            expense.amount = Decimal('8.50')  # Small amount
            expense.category = 'food'
            expense.date = base_date + timedelta(days=day, hours=purchase*4)
            expense.description = "Small purchase"
            expense.spent_at = expense.date
            expense.created_at = expense.date
            expenses.append(expense)

    return expenses

@pytest.fixture
def sample_expenses_with_anomaly():
    """Sample expenses with statistical outlier"""
    expenses = []
    base_date = datetime.utcnow() - timedelta(days=30)

    # Normal expenses ($50 each)
    for day in range(29):
        expense = Mock()
        expense.amount = Decimal('50.00')
        expense.category = 'food'
        expense.date = base_date + timedelta(days=day)
        expense.description = f"Normal expense {day}"
        expense.spent_at = expense.date
        expense.created_at = expense.date
        expenses.append(expense)

    # Anomaly (3x higher than normal)
    anomaly = Mock()
    anomaly.amount = Decimal('500.00')  # Huge outlier
    anomaly.category = 'food'
    anomaly.date = base_date + timedelta(days=29)
    anomaly.description = "Unusual large purchase"
    anomaly.spent_at = anomaly.date
    anomaly.created_at = anomaly.date
    expenses.append(anomaly)

    return expenses

@pytest.fixture
def sample_expenses_subscriptions():
    """Sample expenses with recurring subscriptions (6+ unique to trigger accumulation)"""
    expenses = []
    base_date = datetime.utcnow() - timedelta(days=180)  # 6 months

    # Define subscriptions with different categories/amounts so keys are unique
    subscriptions = [
        ('Netflix subscription', Decimal('15.99'), 'entertainment'),
        ('Spotify Premium', Decimal('9.99'), 'entertainment'),
        ('Amazon Prime monthly', Decimal('14.99'), 'shopping'),
        ('Gym membership', Decimal('29.99'), 'health'),
        ('Cloud subscription monthly', Decimal('12.99'), 'utilities'),
        ('Premium news subscription', Decimal('19.99'), 'education'),
    ]

    # Monthly recurring charges
    for month in range(6):
        for desc, amount, category in subscriptions:
            expense = Mock()
            expense.amount = amount
            expense.category = category
            expense.date = base_date + timedelta(days=month*30, hours=subscriptions.index((desc, amount, category)))
            expense.description = desc
            expense.spent_at = expense.date
            expense.created_at = expense.date
            expenses.append(expense)

    return expenses

@pytest.fixture
def sample_expenses_impulse_buying():
    """Sample expenses with impulse buying indicators"""
    expenses = []
    base_date = datetime.utcnow() - timedelta(days=30)

    for i in range(10):
        expense = Mock()
        expense.amount = Decimal('120.00')
        expense.category = 'shopping'
        expense.date = base_date + timedelta(days=i*3)
        expense.description = "SALE! Special offer 50% OFF"  # Impulse keywords
        expense.spent_at = expense.date
        expense.created_at = expense.date
        expenses.append(expense)

    return expenses

# ============================================================================
# TESTS: SPENDING PATTERN DETECTION
# ============================================================================

class TestSpendingPatternDetection:
    """Test ML-based spending pattern detection algorithms"""

    def test_weekend_overspending_detection(self, mock_db, test_user_id, sample_expenses_weekend_pattern):
        """Test detection of weekend vs weekday spending patterns"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            # Convert Mock objects to dicts for analyzer
            mock_load.return_value = [
                {
                    'amount': float(e.amount),
                    'category': e.category,
                    'date': e.date,
                    'description': e.description
                }
                for e in sample_expenses_weekend_pattern
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.analyze_spending_patterns()

            assert 'patterns' in result
            assert 'weekend_overspending' in result['patterns']
            assert result['confidence'] > 0.3
            assert result['data_points'] >= 60

    def test_frequent_small_purchases_detection(self, mock_db, test_user_id, sample_expenses_small_purchases):
        """Test detection of frequent small purchases pattern"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = [
                {
                    'amount': float(e.amount),
                    'category': e.category,
                    'date': e.date,
                    'description': e.description
                }
                for e in sample_expenses_small_purchases
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.analyze_spending_patterns()

            assert 'patterns' in result
            assert 'frequent_small_purchases' in result['patterns']

    def test_impulse_buying_detection(self, mock_db, test_user_id, sample_expenses_impulse_buying):
        """Test detection of impulse buying patterns via keywords"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = [
                {
                    'amount': float(e.amount),
                    'category': e.category,
                    'date': e.date,
                    'description': e.description
                }
                for e in sample_expenses_impulse_buying
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.analyze_spending_patterns()

            assert 'patterns' in result
            assert 'impulse_buying' in result['patterns']

    def test_subscription_accumulation_detection(self, mock_db, test_user_id, sample_expenses_subscriptions):
        """Test detection of recurring subscription payments"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = [
                {
                    'amount': float(e.amount),
                    'category': e.category,
                    'date': e.date,
                    'description': e.description
                }
                for e in sample_expenses_subscriptions
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.analyze_spending_patterns()

            assert 'patterns' in result
            assert 'subscription_accumulation' in result['patterns']

    def test_no_patterns_insufficient_data(self, mock_db, test_user_id):
        """Test graceful handling when insufficient data for patterns"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            # Only 5 data points spread across categories to avoid category_concentration
            categories = ['food', 'transportation', 'entertainment', 'shopping', 'utilities']
            mock_load.return_value = [
                {'amount': 50.0, 'category': categories[i], 'date': datetime.utcnow() - timedelta(days=i), 'description': 'test'}
                for i in range(5)
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.analyze_spending_patterns()

            assert result['patterns'] == []
            assert result['confidence'] < 0.5

# ============================================================================
# TESTS: ANOMALY DETECTION
# ============================================================================

class TestAnomalyDetection:
    """Test statistical anomaly detection (2σ outliers)"""

    def test_detect_high_severity_anomaly(self, mock_db, test_user_id, sample_expenses_with_anomaly):
        """Test detection of high severity spending anomaly"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = [
                {
                    'amount': float(e.amount),
                    'category': e.category,
                    'date': e.date,
                    'description': e.description
                }
                for e in sample_expenses_with_anomaly
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            anomalies = analyzer.detect_spending_anomalies()

            assert len(anomalies) > 0
            assert anomalies[0]['amount'] == 500.00
            assert anomalies[0]['severity'] in ['high', 'medium']
            assert anomalies[0]['category'] == 'food'

    def test_no_anomalies_consistent_spending(self, mock_db, test_user_id):
        """Test no anomalies detected with consistent spending"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            # All expenses exactly the same
            mock_load.return_value = [
                {'amount': 50.0, 'category': 'food', 'date': datetime.utcnow() - timedelta(days=i), 'description': 'test'}
                for i in range(30)
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            anomalies = analyzer.detect_spending_anomalies()

            assert len(anomalies) == 0

    def test_anomaly_detection_insufficient_data(self, mock_db, test_user_id):
        """Test anomaly detection with insufficient data (<30 points)"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = [
                {'amount': 50.0, 'category': 'food', 'date': datetime.utcnow(), 'description': 'test'}
                for _ in range(10)
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            anomalies = analyzer.detect_spending_anomalies()

            assert anomalies == []

# ============================================================================
# TESTS: FINANCIAL HEALTH SCORE
# ============================================================================

class TestFinancialHealthScore:
    """Test comprehensive financial health scoring algorithm"""

    def test_calculate_health_score_balanced_spending(self, mock_db, test_user_id):
        """Test health score with balanced spending"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            # Create balanced spending data
            expenses = []
            base_date = datetime.utcnow() - timedelta(days=90)
            for day in range(90):
                expenses.append({
                    'amount': 50.0,
                    'category': 'food' if day % 3 == 0 else 'transportation',
                    'date': base_date + timedelta(days=day),
                    'description': 'expense'
                })
            mock_load.return_value = expenses

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.calculate_financial_health_score()

            assert 'score' in result
            assert 0 <= result['score'] <= 100
            assert 'grade' in result
            assert result['grade'] in ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F']
            assert 'components' in result
            assert 'budgeting' in result['components']
            assert 'spending_efficiency' in result['components']
            assert 'consistency' in result['components']

    def test_health_score_components_validation(self, mock_db, test_user_id):
        """Test that all health score components are calculated"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = [
                {'amount': 50.0, 'category': 'food', 'date': datetime.utcnow() - timedelta(days=i), 'description': 'test'}
                for i in range(60)
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.calculate_financial_health_score()

            components = result['components']
            assert 0 <= components['budgeting'] <= 100
            assert 0 <= components['spending_efficiency'] <= 100
            assert 0 <= components['consistency'] <= 100

    def test_health_score_trend_calculation(self, mock_db, test_user_id):
        """Test trend calculation (improving/stable/declining)"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = [
                {'amount': 50.0, 'category': 'food', 'date': datetime.utcnow() - timedelta(days=i), 'description': 'test'}
                for i in range(60)
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.calculate_financial_health_score()

            assert 'trend' in result
            assert result['trend'] in ['improving', 'stable', 'declining']

# ============================================================================
# TESTS: SAVINGS OPTIMIZATION
# ============================================================================

class TestSavingsOptimization:
    """Test savings optimization suggestions algorithm"""

    def test_savings_optimization_with_subscriptions(self, mock_db, test_user_id, sample_expenses_subscriptions):
        """Test savings suggestions detect subscriptions"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = [
                {
                    'amount': float(e.amount),
                    'category': e.category,
                    'date': e.date,
                    'description': e.description
                }
                for e in sample_expenses_subscriptions
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.generate_savings_optimization()

            assert 'potential_savings' in result
            assert result['potential_savings'] >= 0
            assert 'suggestions' in result
            assert len(result['suggestions']) > 0
            assert 'difficulty_level' in result
            assert result['difficulty_level'] in ['easy', 'moderate', 'challenging']

    def test_savings_optimization_no_opportunities(self, mock_db, test_user_id):
        """Test savings optimization with minimal spending"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            # Very minimal spending - hard to optimize
            mock_load.return_value = [
                {'amount': 10.0, 'category': 'food', 'date': datetime.utcnow() - timedelta(days=i), 'description': 'test'}
                for i in range(10)
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.generate_savings_optimization()

            assert result['potential_savings'] >= 0
            assert 'suggestions' in result

# ============================================================================
# TESTS: DYNAMIC THRESHOLDS
# ============================================================================

class TestDynamicThresholds:
    """Test dynamic threshold adaptation based on user income"""

    def test_thresholds_low_income_user(self, mock_db, low_income_user):
        """Test thresholds for low income user"""
        with patch.object(AIFinancialAnalyzer, '_get_user_context') as mock_context:
            mock_context.return_value = UserContext(
                monthly_income=low_income_user.monthly_income,
                age=low_income_user.age,
                region=low_income_user.region,
                family_size=low_income_user.family_size,
                housing_status=low_income_user.housing_status,
                life_stage=low_income_user.life_stage,
            )

            analyzer = AIFinancialAnalyzer(mock_db, low_income_user.id)
            thresholds = analyzer._get_dynamic_thresholds()

            assert 'spending_patterns' in thresholds
            small_purchase_threshold = thresholds['spending_patterns']['small_purchase_threshold']

            # Low income should have lower thresholds
            assert small_purchase_threshold < 50

    def test_thresholds_high_income_user(self, mock_db, high_income_user):
        """Test thresholds for high income user"""
        with patch.object(AIFinancialAnalyzer, '_get_user_context') as mock_context:
            mock_context.return_value = UserContext(
                monthly_income=high_income_user.monthly_income,
                age=high_income_user.age,
                region=high_income_user.region,
                family_size=high_income_user.family_size,
                housing_status=high_income_user.housing_status,
                life_stage=high_income_user.life_stage,
            )

            analyzer = AIFinancialAnalyzer(mock_db, high_income_user.id)
            thresholds = analyzer._get_dynamic_thresholds()

            small_purchase_threshold = thresholds['spending_patterns']['small_purchase_threshold']

            # High income should have higher thresholds
            assert small_purchase_threshold > 50

    def test_thresholds_scale_with_income(self, mock_db, low_income_user, high_income_user):
        """Test that thresholds properly scale with income"""
        with patch.object(AIFinancialAnalyzer, '_get_user_context') as mock_context:
            # Low income thresholds
            mock_context.return_value = UserContext(
                monthly_income=2000, age=25, region="US",
                family_size=1, housing_status="rent", life_stage="single",
            )
            analyzer_low = AIFinancialAnalyzer(mock_db, low_income_user.id)
            thresholds_low = analyzer_low._get_dynamic_thresholds()

            # High income thresholds
            mock_context.return_value = UserContext(
                monthly_income=15000, age=40, region="US",
                family_size=4, housing_status="own", life_stage="married_with_children",
            )
            analyzer_high = AIFinancialAnalyzer(mock_db, high_income_user.id)
            thresholds_high = analyzer_high._get_dynamic_thresholds()

            # High income thresholds should be significantly higher
            assert (thresholds_high['spending_patterns']['small_purchase_threshold'] >
                    thresholds_low['spending_patterns']['small_purchase_threshold'])

# ============================================================================
# TESTS: WEEKLY INSIGHTS
# ============================================================================

class TestWeeklyInsights:
    """Test weekly insights generation"""

    def test_weekly_insights_increasing_trend(self, mock_db, test_user_id):
        """Test weekly insights with increasing spending trend"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            # Align dates with the algorithm's week boundaries
            now = datetime.utcnow()
            current_week_start = now - timedelta(days=now.weekday())
            previous_week_start = current_week_start - timedelta(days=7)
            expenses = []

            # Previous week: $280 total (low spending)
            for day in range(7):
                expenses.append({
                    'amount': 40.0,
                    'category': 'food',
                    'date': previous_week_start + timedelta(days=day, hours=12),
                    'description': 'previous week'
                })

            # Current week: $490 total (high spending = increase)
            for day in range(7):
                expenses.append({
                    'amount': 70.0,
                    'category': 'food',
                    'date': current_week_start + timedelta(days=day, hours=12),
                    'description': 'current week'
                })

            mock_load.return_value = expenses

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.generate_weekly_insights()

            assert 'trend' in result
            assert result['trend'] == 'increasing'
            assert 'weekly_summary' in result

    def test_weekly_insights_insufficient_data(self, mock_db, test_user_id):
        """Test weekly insights with insufficient data"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = [
                {'amount': 50.0, 'category': 'food', 'date': datetime.utcnow(), 'description': 'test'}
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.generate_weekly_insights()

            assert 'insights' in result

# ============================================================================
# TESTS: PERSONALIZED FEEDBACK
# ============================================================================

class TestPersonalizedFeedback:
    """Test personalized feedback generation"""

    def test_personalized_feedback_with_patterns(self, mock_db, test_user_id, sample_expenses_weekend_pattern):
        """Test feedback generation with detected patterns"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = [
                {
                    'amount': float(e.amount),
                    'category': e.category,
                    'date': e.date,
                    'description': e.description
                }
                for e in sample_expenses_weekend_pattern
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.generate_personalized_feedback()

            assert 'feedback' in result
            assert isinstance(result['feedback'], str)
            assert len(result['feedback']) > 20  # Should be substantial
            assert 'tips' in result
            assert isinstance(result['tips'], list)
            assert 'confidence' in result
            assert 0.0 <= result['confidence'] <= 1.0

    def test_personalized_feedback_insufficient_data(self, mock_db, test_user_id):
        """Test feedback with minimal data"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = []

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            result = analyzer.generate_personalized_feedback()

            assert 'feedback' in result
            assert 'track' in result['feedback'].lower()  # Should suggest tracking

# ============================================================================
# TESTS: CATEGORY CONCENTRATION (HHI)
# ============================================================================

class TestCategoryConcentration:
    """Test Herfindahl-Hirschman Index for category concentration"""

    def test_high_concentration_single_category(self, mock_db, test_user_id):
        """Test HHI with all spending in one category"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            # All food category
            mock_load.return_value = [
                {'amount': 100.0, 'category': 'food', 'date': datetime.utcnow() - timedelta(days=i), 'description': 'test'}
                for i in range(30)
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            spending_data = analyzer._load_spending_data()
            concentration = analyzer._analyze_category_concentration(spending_data)

            # Perfect concentration should be 1.0
            assert concentration == pytest.approx(1.0, rel=0.01)

    def test_low_concentration_balanced_categories(self, mock_db, test_user_id):
        """Test HHI with balanced spending across categories"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            # Evenly distributed across 4 categories
            expenses = []
            categories = ['food', 'transportation', 'entertainment', 'shopping']
            for i in range(40):
                expenses.append({
                    'amount': 100.0,
                    'category': categories[i % 4],
                    'date': datetime.utcnow() - timedelta(days=i),
                    'description': 'test'
                })
            mock_load.return_value = expenses

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)
            spending_data = analyzer._load_spending_data()
            concentration = analyzer._analyze_category_concentration(spending_data)

            # Well-balanced should be closer to 0.25 (1/4 categories)
            assert concentration < 0.5

# ============================================================================
# TESTS: EDGE CASES & ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_spending_data(self, mock_db, test_user_id):
        """Test all methods with empty spending data"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = []

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)

            # All methods should handle empty data gracefully
            patterns = analyzer.analyze_spending_patterns()
            assert patterns['patterns'] == []

            anomalies = analyzer.detect_spending_anomalies()
            assert anomalies == []

            health = analyzer.calculate_financial_health_score()
            assert 'score' in health

            savings = analyzer.generate_savings_optimization()
            assert 'potential_savings' in savings

    def test_single_expense_entry(self, mock_db, test_user_id):
        """Test with only one expense entry"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = [
                {'amount': 50.0, 'category': 'food', 'date': datetime.utcnow(), 'description': 'test'}
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)

            # Should not crash
            result = analyzer.analyze_spending_patterns()
            assert isinstance(result, dict)

    def test_negative_amounts_handling(self, mock_db, test_user_id):
        """Test handling of negative amounts (refunds)"""
        with patch.object(AIFinancialAnalyzer, '_load_spending_data') as mock_load:
            mock_load.return_value = [
                {'amount': -50.0, 'category': 'food', 'date': datetime.utcnow(), 'description': 'refund'},
                {'amount': 100.0, 'category': 'food', 'date': datetime.utcnow(), 'description': 'purchase'}
            ]

            analyzer = AIFinancialAnalyzer(mock_db, test_user_id)

            # Should handle without crashing
            result = analyzer.analyze_spending_patterns()
            assert isinstance(result, dict)
