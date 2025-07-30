"""
Comprehensive tests for AI Financial Analyzer
Tests all ML algorithms, pattern detection, and financial analysis features
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.services.ai_financial_analyzer import AIFinancialAnalyzer
from app.db.models import User, Expense, Transaction


class TestAIFinancialAnalyzer:
    """Test suite for AI Financial Analyzer"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_db = Mock(spec=Session)
        self.user_id = 123
        self.analyzer = AIFinancialAnalyzer(self.mock_db, self.user_id)
        
        # Mock user
        self.mock_user = Mock(spec=User)
        self.mock_user.id = self.user_id
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_user

    def create_mock_expenses(self, count=50, days_back=60):
        """Create mock expense data for testing"""
        expenses = []
        base_date = datetime.utcnow() - timedelta(days=days_back)
        
        categories = ['food', 'transportation', 'entertainment', 'shopping', 'utilities']
        
        for i in range(count):
            expense = Mock(spec=Expense)
            expense.amount = 20 + (i % 100)  # Varying amounts
            expense.category = categories[i % len(categories)]
            expense.date = base_date + timedelta(days=i % days_back)
            expense.description = f"Test expense {i}"
            expenses.append(expense)
        
        return expenses

    def test_initialization(self):
        """Test analyzer initialization"""
        assert self.analyzer.db == self.mock_db
        assert self.analyzer.user_id == self.user_id
        assert self.analyzer.user == self.mock_user

    def test_analyze_spending_patterns_no_data(self):
        """Test spending pattern analysis with no data"""
        # Mock empty expense query
        self.mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = self.analyzer.analyze_spending_patterns()
        
        assert result['patterns'] == []
        assert result['confidence'] == 0.0
        assert 'analysis_date' in result

    def test_analyze_spending_patterns_with_data(self):
        """Test spending pattern analysis with real data"""
        # Create mock expenses with patterns
        expenses = self.create_mock_expenses(100, 90)
        
        # Add weekend overspending pattern
        for expense in expenses[::7]:  # Every 7th expense (simulate weekend)
            expense.amount = 150  # Higher weekend amounts
            expense.date = expense.date.replace(weekday=5)  # Saturday
        
        # Add small purchases pattern
        for expense in expenses[:60]:  # First 60% are small
            expense.amount = 15
        
        self.mock_db.query.return_value.filter.return_value.all.return_value = expenses
        
        result = self.analyzer.analyze_spending_patterns()
        
        assert isinstance(result['patterns'], list)
        assert result['confidence'] > 0
        assert 'weekend_overspending' in result['patterns'] or 'frequent_small_purchases' in result['patterns']
        assert len(result['patterns']) <= 5

    def test_weekend_vs_weekday_analysis(self):
        """Test weekend vs weekday spending analysis"""
        expenses_data = []
        
        # Add weekday expenses (lower amounts)
        for i in range(20):
            expenses_data.append({
                'amount': 25.0,
                'category': 'food',
                'date': datetime(2025, 1, 6 + i),  # Monday onwards
                'description': 'Weekday expense'
            })
        
        # Add weekend expenses (higher amounts) 
        for i in range(10):
            expenses_data.append({
                'amount': 80.0,
                'category': 'entertainment',
                'date': datetime(2025, 1, 11 + (i * 7)),  # Saturdays
                'description': 'Weekend expense'
            })
        
        weekend_avg, weekday_avg = self.analyzer._analyze_weekend_patterns(expenses_data)
        
        assert weekend_avg > weekday_avg
        assert weekend_avg == 80.0
        assert weekday_avg == 25.0

    def test_category_concentration_analysis(self):
        """Test category spending concentration analysis"""
        # High concentration scenario
        high_concentration_data = [
            {'amount': 100, 'category': 'food'} for _ in range(8)
        ] + [
            {'amount': 10, 'category': 'other'} for _ in range(2)
        ]
        
        concentration = self.analyzer._analyze_category_concentration(high_concentration_data)
        assert concentration > 0.5  # High concentration
        
        # Low concentration scenario
        low_concentration_data = [
            {'amount': 20, 'category': f'category_{i}'} for i in range(10)
        ]
        
        concentration = self.analyzer._analyze_category_concentration(low_concentration_data)
        assert concentration < 0.5  # More distributed

    def test_monthly_variance_analysis(self):
        """Test monthly spending variance calculation"""
        # Create expenses with high variance
        high_variance_data = []
        months = ['2025-01', '2025-02', '2025-03']
        amounts = [100, 500, 200]  # High variance
        
        for month, amount in zip(months, amounts):
            high_variance_data.append({
                'amount': amount,
                'date': datetime.strptime(f'{month}-15', '%Y-%m-%d')
            })
        
        variance = self.analyzer._analyze_monthly_variance(high_variance_data)
        assert variance > 0.3  # High variance
        
        # Create expenses with low variance
        low_variance_data = []
        for month in months:
            low_variance_data.append({
                'amount': 300,  # Consistent amount
                'date': datetime.strptime(f'{month}-15', '%Y-%m-%d')
            })
        
        variance = self.analyzer._analyze_monthly_variance(low_variance_data)
        assert variance < 0.1  # Low variance

    def test_impulse_buying_detection(self):
        """Test impulse buying pattern detection"""
        # High impulse buying scenario
        impulse_data = [
            {'amount': 100, 'category': 'shopping', 'description': 'sale item discount offer'},
            {'amount': 75, 'category': 'entertainment', 'description': 'deal special offer'},
            {'amount': 50, 'category': 'shopping', 'description': 'regular purchase'},
        ]
        
        impulse_score = self.analyzer._detect_impulse_buying(impulse_data)
        assert impulse_score > 0.5  # High impulse score
        
        # Low impulse buying scenario
        regular_data = [
            {'amount': 50, 'category': 'food', 'description': 'grocery shopping'},
            {'amount': 30, 'category': 'transportation', 'description': 'gas'},
            {'amount': 25, 'category': 'utilities', 'description': 'electric bill'},
        ]
        
        impulse_score = self.analyzer._detect_impulse_buying(regular_data)
        assert impulse_score < 0.3  # Low impulse score

    def test_subscription_detection(self):
        """Test subscription detection"""
        subscription_data = [
            {'description': 'netflix subscription', 'category': 'entertainment', 'amount': 15.99},
            {'description': 'spotify premium', 'category': 'entertainment', 'amount': 9.99},
            {'description': 'gym membership monthly', 'category': 'health', 'amount': 49.99},
            {'description': 'amazon prime plus', 'category': 'shopping', 'amount': 12.99},
        ]
        
        subscription_count = self.analyzer._detect_subscriptions(subscription_data)
        assert subscription_count >= 3  # Should detect most subscriptions

    def test_generate_personalized_feedback_no_data(self):
        """Test feedback generation with no data"""
        self.mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = self.analyzer.generate_personalized_feedback()
        
        assert 'Start tracking' in result['feedback']
        assert result['confidence'] == 0.0
        assert result['category_focus'] == 'general'

    def test_generate_personalized_feedback_with_data(self):
        """Test feedback generation with spending data"""
        expenses = self.create_mock_expenses(50, 60)
        self.mock_db.query.return_value.filter.return_value.all.return_value = expenses
        
        result = self.analyzer.generate_personalized_feedback()
        
        assert isinstance(result['feedback'], str)
        assert len(result['feedback']) > 0
        assert isinstance(result['tips'], list)
        assert len(result['tips']) <= 4
        assert result['confidence'] > 0
        assert 'spending_score' in result

    def test_calculate_financial_health_score_no_data(self):
        """Test financial health score with no data"""
        self.mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = self.analyzer.calculate_financial_health_score()
        
        assert result['score'] == 50  # Neutral score
        assert result['grade'] == 'C'
        assert 'components' in result
        assert 'improvements' in result
        assert result['trend'] == 'stable'

    def test_calculate_financial_health_score_with_data(self):
        """Test financial health score calculation with data"""
        expenses = self.create_mock_expenses(100, 120)
        self.mock_db.query.return_value.filter.return_value.all.return_value = expenses
        
        result = self.analyzer.calculate_financial_health_score()
        
        assert 0 <= result['score'] <= 100
        assert result['grade'] in ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F']
        assert all(key in result['components'] for key in ['budgeting', 'spending_efficiency', 'saving_potential', 'consistency'])
        assert isinstance(result['improvements'], list)
        assert result['trend'] in ['improving', 'declining', 'stable']

    def test_score_to_grade_conversion(self):
        """Test score to grade conversion"""
        assert self.analyzer._score_to_grade(95) == 'A+'
        assert self.analyzer._score_to_grade(85) == 'A'
        assert self.analyzer._score_to_grade(80) == 'B+'
        assert self.analyzer._score_to_grade(75) == 'B'
        assert self.analyzer._score_to_grade(70) == 'C+'
        assert self.analyzer._score_to_grade(65) == 'C'
        assert self.analyzer._score_to_grade(60) == 'D+'
        assert self.analyzer._score_to_grade(55) == 'D'
        assert self.analyzer._score_to_grade(50) == 'F'

    def test_detect_spending_anomalies_insufficient_data(self):
        """Test anomaly detection with insufficient data"""
        expenses = self.create_mock_expenses(5, 30)  # Too few for analysis
        self.mock_db.query.return_value.filter.return_value.all.return_value = expenses
        
        result = self.analyzer.detect_spending_anomalies()
        
        assert result == []

    def test_detect_spending_anomalies_with_outliers(self):
        """Test anomaly detection with clear outliers"""
        expenses = self.create_mock_expenses(50, 60)
        
        # Add clear outliers
        outlier_expense = Mock(spec=Expense)
        outlier_expense.amount = 500  # Much higher than normal
        outlier_expense.category = 'food'
        outlier_expense.date = datetime.utcnow() - timedelta(days=10)
        expenses.append(outlier_expense)
        
        self.mock_db.query.return_value.filter.return_value.all.return_value = expenses
        
        result = self.analyzer.detect_spending_anomalies()
        
        assert len(result) >= 1
        assert all('amount' in anomaly for anomaly in result)
        assert all('severity' in anomaly for anomaly in result)
        assert all('description' in anomaly for anomaly in result)

    def test_generate_savings_optimization_no_data(self):
        """Test savings optimization with no data"""
        self.mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = self.analyzer.generate_savings_optimization()
        
        assert result['potential_savings'] == 0.0
        assert 'Start tracking' in result['suggestions'][0]
        assert result['difficulty_level'] == 'easy'
        assert result['impact_score'] == 0.0

    def test_generate_savings_optimization_with_data(self):
        """Test savings optimization with spending data"""
        expenses = self.create_mock_expenses(60, 90)
        
        # Add subscription-like expenses
        for i in range(5):
            expense = Mock(spec=Expense)
            expense.amount = 15.99
            expense.category = 'entertainment'
            expense.description = f'subscription service {i}'
            expense.date = datetime.utcnow() - timedelta(days=i*30)
            expenses.append(expense)
        
        self.mock_db.query.return_value.filter.return_value.all.return_value = expenses
        
        result = self.analyzer.generate_savings_optimization()
        
        assert result['potential_savings'] >= 0
        assert isinstance(result['suggestions'], list)
        assert len(result['suggestions']) <= 4
        assert result['difficulty_level'] in ['easy', 'moderate', 'challenging']
        assert 0 <= result['impact_score'] <= 10

    def test_generate_weekly_insights_no_data(self):
        """Test weekly insights with no data"""
        self.mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = self.analyzer.generate_weekly_insights()
        
        assert 'Start tracking' in result['insights']
        assert result['trend'] == 'stable'
        assert result['weekly_summary'] == {}

    def test_generate_weekly_insights_with_data(self):
        """Test weekly insights with current and previous week data"""
        expenses = []
        
        # Current week expenses
        current_week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
        for i in range(5):
            expense = Mock(spec=Expense)
            expense.amount = 50
            expense.category = 'food'
            expense.date = current_week_start + timedelta(days=i)
            expenses.append(expense)
        
        # Previous week expenses (higher amounts)
        previous_week_start = current_week_start - timedelta(days=7)
        for i in range(5):
            expense = Mock(spec=Expense)
            expense.amount = 80  # Higher than current week
            expense.category = 'food'
            expense.date = previous_week_start + timedelta(days=i)
            expenses.append(expense)
        
        self.mock_db.query.return_value.filter.return_value.all.return_value = expenses
        
        result = self.analyzer.generate_weekly_insights()
        
        assert isinstance(result['insights'], str)
        assert result['trend'] in ['increasing', 'decreasing', 'stable']
        assert 'weekly_summary' in result
        assert 'total_spent' in result['weekly_summary']
        assert 'vs_last_week' in result['weekly_summary']
        assert isinstance(result['recommendations'], list)

    def test_calculate_spending_score(self):
        """Test spending efficiency score calculation"""
        # Test with consistent, well-distributed spending
        good_expenses = []
        categories = ['food', 'transportation', 'entertainment', 'utilities']
        
        for i in range(40):
            good_expenses.append({
                'amount': 50 + (i % 20),  # Moderate variance
                'category': categories[i % len(categories)],
                'date': datetime.utcnow() - timedelta(days=i),
                'description': 'Regular expense'
            })
        
        score = self.analyzer._calculate_spending_score(good_expenses)
        assert 5.0 <= score <= 10.0  # Should be decent score
        
        # Test with poor spending patterns
        bad_expenses = []
        for i in range(40):
            bad_expenses.append({
                'amount': 25 if i % 10 != 0 else 300,  # High variance
                'category': 'entertainment',  # All same category
                'date': datetime.utcnow() - timedelta(days=i),
                'description': 'sale discount deal offer'  # Impulse keywords
            })
        
        score = self.analyzer._calculate_spending_score(bad_expenses)
        assert score < 7.0  # Should be lower score


@pytest.fixture
def mock_database_session():
    """Fixture for mocked database session"""
    return Mock(spec=Session)


@pytest.fixture
def sample_user():
    """Fixture for sample user"""
    user = Mock(spec=User)
    user.id = 123
    user.email = "test@example.com"
    return user


@pytest.fixture
def ai_analyzer(mock_database_session, sample_user):
    """Fixture for AI analyzer instance"""
    analyzer = AIFinancialAnalyzer(mock_database_session, sample_user.id)
    analyzer.user = sample_user
    return analyzer


class TestAIAnalyzerIntegration:
    """Integration tests for AI analyzer with database"""
    
    def test_full_analysis_pipeline(self, ai_analyzer):
        """Test complete analysis pipeline"""
        # Mock database with comprehensive data
        expenses = []
        
        # Create 3 months of varied expense data
        base_date = datetime.utcnow() - timedelta(days=90)
        categories = ['food', 'transportation', 'entertainment', 'shopping', 'utilities']
        
        for i in range(150):
            expense = Mock(spec=Expense)
            expense.amount = 20 + (i % 80)  # Varying amounts
            expense.category = categories[i % len(categories)]
            expense.date = base_date + timedelta(days=i % 90)
            expense.description = f"Expense {i}"
            
            # Add some patterns
            if i % 10 == 0:  # Weekend overspending
                expense.amount = 150
                expense.category = 'entertainment'
            if i % 15 == 0:  # Subscription pattern
                expense.amount = 12.99
                expense.description = 'subscription monthly'
            
            expenses.append(expense)
        
        ai_analyzer.mock_db.query.return_value.filter.return_value.all.return_value = expenses
        
        # Run all analysis methods
        patterns = ai_analyzer.analyze_spending_patterns()
        feedback = ai_analyzer.generate_personalized_feedback()
        health_score = ai_analyzer.calculate_financial_health_score()
        anomalies = ai_analyzer.detect_spending_anomalies()
        optimization = ai_analyzer.generate_savings_optimization()
        weekly_insights = ai_analyzer.generate_weekly_insights()
        
        # Verify all analyses return valid results
        assert isinstance(patterns['patterns'], list)
        assert patterns['confidence'] > 0
        
        assert isinstance(feedback['feedback'], str)
        assert len(feedback['tips']) > 0
        
        assert 0 <= health_score['score'] <= 100
        assert health_score['grade'] in ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F']
        
        assert isinstance(anomalies, list)
        
        assert optimization['potential_savings'] >= 0
        assert isinstance(optimization['suggestions'], list)
        
        assert isinstance(weekly_insights['insights'], str)
        assert weekly_insights['trend'] in ['increasing', 'decreasing', 'stable']

    @patch('app.services.ai_financial_analyzer.datetime')
    def test_time_dependent_analysis(self, mock_datetime, ai_analyzer):
        """Test analysis behavior with different time periods"""
        # Mock current time
        mock_now = datetime(2025, 1, 30, 12, 0, 0)
        mock_datetime.utcnow.return_value = mock_now
        
        # Test weekly insights with specific dates
        expenses = []
        
        # Current week (Jan 27-30, 2025)
        for day in range(27, 31):
            expense = Mock(spec=Expense)
            expense.amount = 40
            expense.category = 'food'
            expense.date = datetime(2025, 1, day)
            expenses.append(expense)
        
        # Previous week (Jan 20-26, 2025)
        for day in range(20, 27):
            expense = Mock(spec=Expense)
            expense.amount = 60  # Higher than current week
            expense.category = 'food'
            expense.date = datetime(2025, 1, day)
            expenses.append(expense)
        
        ai_analyzer.mock_db.query.return_value.filter.return_value.all.return_value = expenses
        
        weekly_insights = ai_analyzer.generate_weekly_insights()
        
        # Should detect decreasing trend (current week lower than previous)
        assert weekly_insights['trend'] == 'decreasing'
        assert weekly_insights['weekly_summary']['vs_last_week'] < 0