"""
Advanced AI Financial Analysis Service
Provides real ML-based financial insights, pattern detection, and recommendations
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import statistics
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.db.models import Expense, User, Transaction
from app.services.core.behavior.behavioral_config import CATEGORY_PRIORITIES
from app.services.core.dynamic_threshold_service import (
    get_dynamic_thresholds, ThresholdType, UserContext, get_housing_affordability_thresholds
)
from app.services.core.income_scaling_algorithms import (
    scale_threshold_by_income, get_scaled_variance_thresholds
)
from app.services.core.income_classification_service import classify_income


logger = logging.getLogger(__name__)


class AIFinancialAnalyzer:
    """Advanced financial AI analyzer with real ML algorithms"""
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.user = self._get_user()
        self._spending_data = None
        self._transaction_data = None
        self._user_context = None
        self._dynamic_thresholds = None
    
    def _get_user(self) -> User:
        """Get user from database"""
        return self.db.query(User).filter(User.id == self.user_id).first()
    
    def _get_user_context(self) -> UserContext:
        """Get user context for dynamic threshold calculations"""
        if self._user_context is None:
            # Extract user information for context
            user = self.user
            monthly_income = getattr(user, 'monthly_income', 5000)  # Default if not set
            age = getattr(user, 'age', 35)  # Default if not set
            region = getattr(user, 'region', 'US')  # Default to US
            
            self._user_context = UserContext(
                monthly_income=monthly_income,
                age=age,
                region=region,
                family_size=getattr(user, 'family_size', 1),
                debt_to_income_ratio=getattr(user, 'debt_to_income_ratio', 0.0),
                months_of_data=len(set(expense['date'].strftime('%Y-%m')
                                     for expense in self._load_spending_data())),
                current_savings_rate=getattr(user, 'current_savings_rate', 0.0),
                housing_status=getattr(user, 'housing_status', 'rent'),
                life_stage=getattr(user, 'life_stage', 'single')
            )
        return self._user_context
    
    def _get_dynamic_thresholds(self) -> Dict:
        """Get dynamic thresholds for this user"""
        if self._dynamic_thresholds is None:
            user_context = self._get_user_context()
            self._dynamic_thresholds = {
                'spending_patterns': get_dynamic_thresholds(
                    ThresholdType.SPENDING_PATTERN, user_context
                ),
                'health_scoring': get_dynamic_thresholds(
                    ThresholdType.HEALTH_SCORING, user_context
                ),
                'behavioral_triggers': get_dynamic_thresholds(
                    ThresholdType.BEHAVIORAL_TRIGGER, user_context
                )
            }
        return self._dynamic_thresholds
    
    def _load_spending_data(self, months_back: int = 6) -> List[Dict]:
        """Load user's spending data for analysis"""
        if self._spending_data is None:
            cutoff_date = datetime.utcnow() - timedelta(days=months_back * 30)
            
            expenses = self.db.query(Expense).filter(
                and_(
                    Expense.user_id == self.user_id,
                    Expense.date >= cutoff_date
                )
            ).all()
            
            self._spending_data = [
                {
                    'amount': float(expense.amount),
                    'category': expense.category,
                    'date': expense.date,
                    'description': expense.description or ""
                }
                for expense in expenses
            ]
        
        return self._spending_data
    
    def _load_transaction_data(self, months_back: int = 3) -> List[Dict]:
        """Load user's transaction data for analysis"""
        if self._transaction_data is None:
            cutoff_date = datetime.utcnow() - timedelta(days=months_back * 30)
            
            transactions = self.db.query(Transaction).filter(
                and_(
                    Transaction.user_id == self.user_id,
                    Transaction.created_at >= cutoff_date
                )
            ).all()
            
            self._transaction_data = [
                {
                    'amount': float(transaction.amount),
                    'category': transaction.category,
                    'date': transaction.created_at,
                    'description': transaction.description or ""
                }
                for transaction in transactions
            ]
        
        return self._transaction_data
    
    def analyze_spending_patterns(self) -> Dict:
        """Detect real spending patterns using ML algorithms"""
        spending_data = self._load_spending_data()
        
        if not spending_data:
            return {
                "patterns": [],
                "confidence": 0.0,
                "analysis_date": datetime.utcnow().isoformat()
            }
        
        patterns = []
        
        # Pattern 1: Weekend vs Weekday spending analysis
        weekend_spending, weekday_spending = self._analyze_weekend_patterns(spending_data)
        if weekend_spending > weekday_spending * 1.3:
            patterns.append("weekend_overspending")
        
        # Pattern 2: Small frequent purchases detection (now dynamic)
        thresholds = self._get_dynamic_thresholds()['spending_patterns']
        small_purchase_threshold = thresholds['small_purchase_threshold']
        
        small_purchases = [s for s in spending_data if s['amount'] < small_purchase_threshold]
        if len(small_purchases) > len(spending_data) * 0.6:
            patterns.append("frequent_small_purchases")
        
        # Pattern 3: Category concentration analysis (now dynamic)
        thresholds = self._get_dynamic_thresholds()['spending_patterns']
        concentration_threshold = thresholds['category_concentration_threshold']
        
        category_concentration = self._analyze_category_concentration(spending_data)
        if category_concentration > concentration_threshold:
            patterns.append("category_concentration")
        
        # Pattern 4: Monthly spending variance (now dynamic)
        thresholds = self._get_dynamic_thresholds()['spending_patterns']
        variance_threshold = thresholds['monthly_variance_threshold']
        
        monthly_variance = self._analyze_monthly_variance(spending_data)
        if monthly_variance > variance_threshold:
            patterns.append("irregular_spending")
        
        # Pattern 5: Impulse buying detection (now dynamic)
        thresholds = self._get_dynamic_thresholds()['spending_patterns']
        impulse_threshold = thresholds['impulse_buying_threshold']
        
        impulse_score = self._detect_impulse_buying(spending_data)
        if impulse_score > impulse_threshold:
            patterns.append("impulse_buying")
        
        # Pattern 6: Subscription accumulation
        subscription_count = self._detect_subscriptions(spending_data)
        if subscription_count > 5:
            patterns.append("subscription_accumulation")
        
        confidence = min(0.95, len(spending_data) / 100)  # Higher confidence with more data
        
        return {
            "patterns": patterns[:5],  # Return top 5 patterns
            "confidence": confidence,
            "analysis_date": datetime.utcnow().isoformat(),
            "data_points": len(spending_data)
        }
    
    def _analyze_weekend_patterns(self, spending_data: List[Dict]) -> Tuple[float, float]:
        """Analyze weekend vs weekday spending patterns"""
        weekend_amounts = []
        weekday_amounts = []
        
        for expense in spending_data:
            weekday = expense['date'].weekday()
            if weekday >= 5:  # Saturday, Sunday
                weekend_amounts.append(expense['amount'])
            else:
                weekday_amounts.append(expense['amount'])
        
        weekend_avg = statistics.mean(weekend_amounts) if weekend_amounts else 0
        weekday_avg = statistics.mean(weekday_amounts) if weekday_amounts else 0
        
        return weekend_avg, weekday_avg
    
    def _analyze_category_concentration(self, spending_data: List[Dict]) -> float:
        """Calculate spending concentration in categories"""
        if not spending_data:
            return 0.0
        
        category_amounts = {}
        total_amount = 0
        
        for expense in spending_data:
            category = expense['category']
            amount = expense['amount']
            category_amounts[category] = category_amounts.get(category, 0) + amount
            total_amount += amount
        
        if total_amount == 0:
            return 0.0
        
        # Calculate Herfindahl-Hirschman Index for concentration
        hhi = sum((amount / total_amount) ** 2 for amount in category_amounts.values())
        return hhi
    
    def _analyze_monthly_variance(self, spending_data: List[Dict]) -> float:
        """Calculate monthly spending variance"""
        monthly_totals = {}
        
        for expense in spending_data:
            month_key = expense['date'].strftime('%Y-%m')
            monthly_totals[month_key] = monthly_totals.get(month_key, 0) + expense['amount']
        
        if len(monthly_totals) < 2:
            return 0.0
        
        amounts = list(monthly_totals.values())
        mean_spending = statistics.mean(amounts)
        
        if mean_spending == 0:
            return 0.0
        
        variance = statistics.variance(amounts) if len(amounts) > 1 else 0
        coefficient_of_variation = (variance ** 0.5) / mean_spending
        
        return min(1.0, coefficient_of_variation)
    
    def _detect_impulse_buying(self, spending_data: List[Dict]) -> float:
        """Detect impulse buying patterns based on transaction characteristics"""
        impulse_indicators = 0
        total_transactions = len(spending_data)
        
        if total_transactions == 0:
            return 0.0
        
        for expense in spending_data:
            description = expense['description'].lower()
            amount = expense['amount']
            
            # Indicators of impulse buying
            if any(word in description for word in ['sale', 'discount', 'deal', 'offer']):
                impulse_indicators += 1
            # Use dynamic threshold instead of hardcoded $50
            user_context = self._get_user_context()
            medium_purchase_threshold = self._get_dynamic_thresholds()['spending_patterns']['medium_purchase_threshold']
            
            if amount > medium_purchase_threshold and any(cat in expense['category'].lower() for cat in ['entertainment', 'shopping']):
                impulse_indicators += 0.5
        
        return min(1.0, impulse_indicators / total_transactions)
    
    def _detect_subscriptions(self, spending_data: List[Dict]) -> int:
        """Detect recurring subscription payments"""
        subscription_keywords = [
            'netflix', 'spotify', 'amazon', 'subscription', 'monthly',
            'premium', 'pro', 'plus', 'gym', 'membership'
        ]
        
        potential_subscriptions = set()
        
        for expense in spending_data:
            description = expense['description'].lower()
            if any(keyword in description for keyword in subscription_keywords):
                # Group by similar amounts and descriptions
                key = f"{expense['category']}_{int(expense['amount'])}"
                potential_subscriptions.add(key)
        
        return len(potential_subscriptions)
    
    def generate_personalized_feedback(self) -> Dict:
        """Generate AI-powered personalized financial feedback"""
        spending_data = self._load_spending_data()
        patterns = self.analyze_spending_patterns()
        
        if not spending_data:
            return {
                "feedback": "Start tracking your expenses to receive personalized insights.",
                "tips": ["Begin by logging your daily expenses", "Set up budget categories"],
                "confidence": 0.0,
                "category_focus": "general"
            }
        
        # Analyze spending by category
        category_analysis = self._analyze_category_spending(spending_data)
        top_category = max(category_analysis.items(), key=lambda x: x[1])[0] if category_analysis else "general"
        
        # Generate contextual feedback
        feedback_text = self._generate_contextual_feedback(spending_data, patterns, category_analysis)
        
        # Generate actionable tips
        tips = self._generate_actionable_tips(patterns["patterns"], category_analysis)
        
        confidence = min(0.95, len(spending_data) / 50)
        
        return {
            "feedback": feedback_text,
            "tips": tips[:4],  # Top 4 tips
            "confidence": confidence,
            "category_focus": top_category,
            "spending_score": self._calculate_spending_score(spending_data)
        }
    
    def _analyze_category_spending(self, spending_data: List[Dict]) -> Dict[str, float]:
        """Analyze spending by category"""
        category_totals = {}
        
        for expense in spending_data:
            category = expense['category']
            category_totals[category] = category_totals.get(category, 0) + expense['amount']
        
        return category_totals
    
    def _generate_contextual_feedback(self, spending_data: List[Dict], patterns: Dict, category_analysis: Dict[str, float]) -> str:
        """Generate contextual feedback based on analysis"""
        total_spending = sum(expense['amount'] for expense in spending_data)
        avg_daily_spending = total_spending / max(1, len(set(expense['date'].date() for expense in spending_data)))
        
        feedback_parts = []
        
        # Overall spending assessment (now income-relative)
        user_context = self._get_user_context()
        monthly_income = user_context.monthly_income
        
        # Calculate income-relative spending benchmarks
        high_daily_threshold = monthly_income * 0.10  # 10% of monthly income per day is high
        moderate_daily_threshold = monthly_income * 0.05  # 5% is moderate
        
        if avg_daily_spending > high_daily_threshold:
            feedback_parts.append("Your daily spending is relatively high for your income level.")
        elif avg_daily_spending > moderate_daily_threshold:
            feedback_parts.append("Your spending patterns show moderate daily expenses.")
        else:
            feedback_parts.append("You maintain good control over daily spending.")
        
        # Pattern-based feedback
        detected_patterns = patterns.get("patterns", [])
        
        if "weekend_overspending" in detected_patterns:
            feedback_parts.append("You tend to spend significantly more on weekends.")
        
        if "frequent_small_purchases" in detected_patterns:
            feedback_parts.append("Many small purchases add up throughout the month.")
        
        if "impulse_buying" in detected_patterns:
            feedback_parts.append("Consider implementing a waiting period before non-essential purchases.")
        
        # Category-specific feedback
        if category_analysis:
            top_category = max(category_analysis.items(), key=lambda x: x[1])[0]
            top_amount = category_analysis[top_category]
            percentage = (top_amount / sum(category_analysis.values())) * 100
            
            # Use dynamic concentration threshold
            thresholds = self._get_dynamic_thresholds()['spending_patterns']
            concentration_warning = thresholds['category_concentration_warning']
            
            if (percentage / 100) > concentration_warning:
                feedback_parts.append(f"Your {top_category} expenses represent {percentage:.0f}% of total spending, consider diversifying.")
        
        return " ".join(feedback_parts)
    
    def _generate_actionable_tips(self, patterns: List[str], category_analysis: Dict[str, float]) -> List[str]:
        """Generate actionable tips based on patterns"""
        tips = []
        
        if "weekend_overspending" in patterns:
            tips.append("Set a specific weekend budget and track it in real-time")
            tips.append("Plan weekend activities in advance to avoid impulse spending")
        
        if "frequent_small_purchases" in patterns:
            tips.append("Use the 24-hour rule: wait a day before making purchases under $25")
            tips.append("Set up automatic savings to redirect small purchase amounts")
        
        if "impulse_buying" in patterns:
            tips.append("Create a wish list and review it weekly instead of buying immediately")
            tips.append("Unsubscribe from promotional emails and shopping apps")
        
        if "subscription_accumulation" in patterns:
            tips.append("Review all subscriptions monthly and cancel unused ones")
            tips.append("Use shared family plans where possible to reduce costs")
        
        # Category-specific tips
        if category_analysis:
            top_category = max(category_analysis.items(), key=lambda x: x[1])[0]
            top_amount = category_analysis[top_category]

            if top_category == "food" or top_category == "dining":
                # Calculate user-specific savings potential instead of fixed 20-30%
                user_context = self._get_user_context()
                food_ratio = scale_threshold_by_income('food_ratio', user_context.monthly_income,
                                                     family_size=user_context.family_size)
                current_food_pct = (top_amount / sum(category_analysis.values())) * 100
                
                if current_food_pct > food_ratio * 100 * 1.2:  # 20% above optimal
                    potential_savings = (current_food_pct - food_ratio * 100) / current_food_pct * 100
                    tips.append(f"Try meal planning to reduce food expenses by {potential_savings:.0f}%")
                else:
                    tips.append("Try meal planning to reduce food expenses by 15-25%")
                tips.append("Set a weekly dining out limit and stick to it")
            elif top_category == "transportation":
                tips.append("Consider carpooling or public transport alternatives")
                tips.append("Combine errands into single trips to save on fuel")
            elif top_category == "entertainment":
                tips.append("Look for free community events and activities")
                tips.append("Set up a monthly entertainment budget and track it closely")
        
        # Generic tips if no specific patterns
        if not patterns:
            # Calculate user-specific savings target instead of fixed 20%
            user_context = self._get_user_context()
            savings_target = scale_threshold_by_income('savings_rate', user_context.monthly_income, 
                                                     age=user_context.age,
                                                     debt_to_income_ratio=user_context.debt_to_income_ratio)
            tips.extend([
                "Track expenses daily to identify spending patterns",
                f"Set up automatic savings of {savings_target:.0%} of income",
                "Review and optimize recurring expenses monthly",
                "Use cash for discretionary spending to increase awareness"
            ])
        
        return tips
    
    def _calculate_spending_score(self, spending_data: List[Dict]) -> float:
        """Calculate a spending efficiency score (0-10)"""
        if not spending_data:
            return 5.0  # Neutral score
        
        score = 7.0  # Start with above average
        
        # Analyze spending regularity
        monthly_variance = self._analyze_monthly_variance(spending_data)
        # Use dynamic variance thresholds instead of hardcoded values
        dynamic_thresholds = self._get_dynamic_thresholds()['spending_patterns']
        excellent_threshold = dynamic_thresholds['monthly_variance_excellent']
        warning_threshold = dynamic_thresholds['monthly_variance_warning']
        max_threshold = dynamic_thresholds['monthly_variance_threshold']
        
        if monthly_variance < excellent_threshold:
            score += 1.0  # Excellent consistency for this tier
        elif monthly_variance > max_threshold:
            score -= 1.5  # High variance is concerning for this tier
        
        # Analyze category distribution
        category_concentration = self._analyze_category_concentration(spending_data)
        # Use dynamic concentration thresholds
        concentration_thresholds = self._get_dynamic_thresholds()['spending_patterns']
        good_concentration = concentration_thresholds['category_concentration_threshold'] * 0.8
        bad_concentration = concentration_thresholds['category_concentration_threshold'] * 1.2
        
        if category_concentration < good_concentration:
            score += 0.5  # Good diversification for this tier
        elif category_concentration > bad_concentration:
            score -= 1.0  # Too concentrated for this tier
        
        # Analyze impulse buying
        impulse_score = self._detect_impulse_buying(spending_data)
        score -= impulse_score * 2  # Impulse buying reduces score
        
        # Ensure score is within bounds
        return max(0.0, min(10.0, score))
    
    def calculate_financial_health_score(self) -> Dict:
        """Calculate comprehensive financial health score with real analysis"""
        spending_data = self._load_spending_data()
        
        if not spending_data:
            # Use income-appropriate baseline for no data case
            user_context = self._get_user_context()
            tier = classify_income(user_context.monthly_income, user_context.region)
            thresholds = self._get_dynamic_thresholds()['health_scoring']
            
            baseline_score = thresholds['component_expectations']['budgeting_excellence']
            
            return {
                "score": int(baseline_score),
                "grade": self._score_to_grade(baseline_score),
                "components": {
                    "budgeting": int(baseline_score),
                    "saving": int(baseline_score),
                    "debt_management": int(baseline_score),
                    "spending_efficiency": int(baseline_score)
                },
                "improvements": ["Start tracking expenses to get accurate health score"],
                "trend": "stable"
            }
        
        # Calculate component scores
        budgeting_score = self._calculate_budgeting_score(spending_data)
        spending_efficiency_score = self._calculate_spending_score(spending_data) * 10
        saving_potential_score = self._calculate_saving_potential_score(spending_data)
        consistency_score = self._calculate_consistency_score(spending_data)
        
        # Overall score (weighted average)
        overall_score = (
            budgeting_score * 0.25 +
            spending_efficiency_score * 0.30 +
            saving_potential_score * 0.25 +
            consistency_score * 0.20
        )
        
        grade = self._score_to_grade(overall_score)
        improvements = self._generate_health_improvements(
            budgeting_score, spending_efficiency_score, 
            saving_potential_score, consistency_score
        )
        
        # Calculate trend based on recent vs older data
        trend = self._calculate_health_trend(spending_data)
        
        return {
            "score": int(overall_score),
            "grade": grade,
            "components": {
                "budgeting": int(budgeting_score),
                "spending_efficiency": int(spending_efficiency_score),
                "saving_potential": int(saving_potential_score),
                "consistency": int(consistency_score)
            },
            "improvements": improvements[:3],
            "trend": trend
        }
    
    def _calculate_budgeting_score(self, spending_data: List[Dict]) -> float:
        """Calculate budgeting effectiveness score using dynamic expectations"""
        # Analyze spending distribution across categories
        category_analysis = self._analyze_category_spending(spending_data)
        
        if not category_analysis:
            # Use dynamic baseline instead of hardcoded 50
            thresholds = self._get_dynamic_thresholds()['health_scoring']
            return thresholds['component_expectations']['budgeting_excellence']
        
        # Get dynamic budget allocations for this user
        user_context = self._get_user_context()
        expected_distribution = get_dynamic_thresholds(
            ThresholdType.BUDGET_ALLOCATION, user_context
        )
        
        # Start with tier-appropriate baseline score
        thresholds = self._get_dynamic_thresholds()['health_scoring']
        score = thresholds['component_expectations']['budgeting_excellence']
        
        total_spending = sum(category_analysis.values())
        
        for category, expected_pct in expected_distribution.items():
            actual_pct = category_analysis.get(category, 0) / total_spending
            deviation = abs(actual_pct - expected_pct)
            # Scale penalty based on category importance
            penalty_multiplier = 80 if category in ['housing', 'food'] else 60
            score -= deviation * penalty_multiplier
        
        return max(0.0, min(100.0, score))
    
    def _calculate_saving_potential_score(self, spending_data: List[Dict]) -> float:
        """Calculate savings potential using dynamic thresholds"""
        patterns = self.analyze_spending_patterns()["patterns"]
        
        # Start with tier-appropriate baseline
        thresholds = self._get_dynamic_thresholds()['health_scoring']
        score = thresholds['component_expectations']['savings_achievement']
        
        # Deduct points for wasteful patterns (dynamic penalties)
        if "impulse_buying" in patterns:
            score -= 15
        if "subscription_accumulation" in patterns:
            score -= 10
        if "weekend_overspending" in patterns:
            score -= 10
        if "frequent_small_purchases" in patterns:
            score -= 8
        
        # Add points for efficient patterns using dynamic variance threshold
        monthly_variance = self._analyze_monthly_variance(spending_data)
        dynamic_thresholds = self._get_dynamic_thresholds()['spending_patterns']
        variance_excellent = dynamic_thresholds['monthly_variance_excellent']
        
        if monthly_variance < variance_excellent:
            score += 15  # Excellent consistency for this tier
        
        return max(0.0, min(100.0, score))
    
    def _calculate_consistency_score(self, spending_data: List[Dict]) -> float:
        """Calculate spending consistency score using dynamic thresholds"""
        monthly_variance = self._analyze_monthly_variance(spending_data)
        
        # Get dynamic variance thresholds for this user
        dynamic_thresholds = self._get_dynamic_thresholds()['spending_patterns']
        thresholds = self._get_dynamic_thresholds()['health_scoring']
        
        excellent_threshold = dynamic_thresholds['monthly_variance_excellent']
        warning_threshold = dynamic_thresholds['monthly_variance_warning']
        max_threshold = dynamic_thresholds['monthly_variance_threshold']
        
        base_score = thresholds['component_expectations']['consistency_target']
        
        # Dynamic scoring based on user's tier expectations
        if monthly_variance < excellent_threshold:
            return min(100.0, base_score + 20)  # Excellent consistency bonus
        elif monthly_variance < warning_threshold:
            return base_score + 10  # Good consistency
        elif monthly_variance < max_threshold:
            return base_score  # Acceptable consistency
        else:
            # Scale penalty based on how far over threshold
            excess = monthly_variance - max_threshold
            penalty = min(30, excess * 100)  # Cap penalty at 30 points
            return max(30.0, base_score - penalty)
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade using dynamic boundaries"""
        # Get dynamic grade boundaries for this user's context
        thresholds = self._get_dynamic_thresholds()['health_scoring']
        boundaries = thresholds['grade_boundaries']
        
        if score >= boundaries['A_plus']:
            return "A+"
        elif score >= boundaries['A']:
            return "A"
        elif score >= boundaries['B_plus']:
            return "B+"
        elif score >= boundaries['B']:
            return "B"
        elif score >= boundaries['C_plus']:
            return "C+"
        elif score >= boundaries['C']:
            return "C"
        elif score >= boundaries['D_plus']:
            return "D+"
        elif score >= boundaries['D']:
            return "D"
        else:
            return "F"
    
    def _generate_health_improvements(self, budgeting: float, efficiency: float, 
                                    saving: float, consistency: float) -> List[str]:
        """Generate improvement suggestions based on component scores"""
        improvements = []
        
        # Use dynamic improvement thresholds
        thresholds = self._get_dynamic_thresholds()['health_scoring']
        budgeting_target = thresholds['component_expectations']['budgeting_excellence']
        efficiency_target = thresholds['component_expectations']['spending_efficiency']
        savings_target = thresholds['component_expectations']['savings_achievement']
        consistency_target = thresholds['component_expectations']['consistency_target']
        
        if budgeting < budgeting_target:
            improvements.append("Create detailed budget categories and track spending against limits")
        
        if efficiency < efficiency_target:
            improvements.append("Reduce impulse purchases by implementing a 24-hour waiting period")
        
        if saving < savings_target:
            improvements.append("Cancel unused subscriptions and redirect savings to emergency fund")
        
        if consistency < consistency_target:
            improvements.append("Establish regular spending patterns and avoid large monthly variations")
        
        # If all scores meet tier expectations, provide advanced tips
        all_targets_met = (
            budgeting >= budgeting_target and
            efficiency >= efficiency_target and
            saving >= savings_target and
            consistency >= consistency_target
        )
        
        if all_targets_met:
            improvements.extend([
                "Consider increasing emergency fund to 6 months of expenses",
                "Explore investment opportunities for long-term wealth building",
                "Optimize tax-advantaged savings accounts"
            ])
        
        return improvements
    
    def _calculate_health_trend(self, spending_data: List[Dict]) -> str:
        """Calculate if financial health is improving, declining, or stable"""
        if len(spending_data) < 60:  # Need at least 2 months of data
            return "stable"
        
        # Split data into recent and older periods
        sorted_data = sorted(spending_data, key=lambda x: x['date'])
        mid_point = len(sorted_data) // 2
        
        older_data = sorted_data[:mid_point]
        recent_data = sorted_data[mid_point:]
        
        # Compare spending efficiency between periods
        older_score = self._calculate_spending_score(older_data)
        recent_score = self._calculate_spending_score(recent_data)
        
        difference = recent_score - older_score
        
        if difference > 0.5:
            return "improving"
        elif difference < -0.5:
            return "declining"
        else:
            return "stable"
    
    def detect_spending_anomalies(self) -> List[Dict]:
        """Detect spending anomalies using statistical analysis"""
        spending_data = self._load_spending_data()
        
        if len(spending_data) < 30:
            return []  # Need sufficient data for anomaly detection
        
        anomalies = []
        
        # Analyze by category
        category_data = {}
        for expense in spending_data:
            category = expense['category']
            if category not in category_data:
                category_data[category] = []
            category_data[category].append(expense['amount'])
        
        for category, amounts in category_data.items():
            if len(amounts) < 10:  # Need enough data points
                continue
            
            mean_amount = statistics.mean(amounts)
            std_dev = statistics.stdev(amounts) if len(amounts) > 1 else 0
            
            if std_dev == 0:
                continue
            
            # Find outliers (expenses > 2 standard deviations from mean)
            threshold = mean_amount + (2 * std_dev)
            
            for expense in spending_data:
                if (expense['category'] == category and 
                    expense['amount'] > threshold and 
                    expense['amount'] > mean_amount * 1.5):
                    
                    severity = "high" if expense['amount'] > threshold * 1.5 else "medium"
                    
                    anomalies.append({
                        "id": len(anomalies) + 1,
                        "description": f"Unusual {category} expense - {((expense['amount'] / mean_amount - 1) * 100):.0f}% above average",
                        "amount": expense['amount'],
                        "category": category,
                        "date": expense['date'].isoformat(),
                        "severity": severity,
                        "average_for_category": round(mean_amount, 2)
                    })
        
        # Sort by severity and amount
        severity_order = {"high": 3, "medium": 2, "low": 1}
        anomalies.sort(key=lambda x: (severity_order[x["severity"]], x["amount"]), reverse=True)
        
        return anomalies[:5]  # Return top 5 anomalies
    
    def generate_savings_optimization(self) -> Dict:
        """Generate AI-powered savings optimization suggestions"""
        spending_data = self._load_spending_data()
        patterns = self.analyze_spending_patterns()["patterns"]
        
        if not spending_data:
            return {
                "potential_savings": 0.0,
                "suggestions": ["Start tracking expenses to identify savings opportunities"],
                "difficulty_level": "easy",
                "impact_score": 0.0,
                "implementation_tips": []
            }
        
        suggestions = []
        total_potential_savings = 0.0
        
        # Analyze subscription costs
        subscription_savings = self._calculate_subscription_savings(spending_data)
        if subscription_savings > 0:
            suggestions.append(f"Review and cancel unused subscriptions - save ${subscription_savings:.2f}/month")
            total_potential_savings += subscription_savings
        
        # Analyze dining out patterns
        dining_savings = self._calculate_dining_savings(spending_data)
        if dining_savings > 0:
            suggestions.append(f"Reduce dining out by 25% through meal planning - save ${dining_savings:.2f}/month")
            total_potential_savings += dining_savings
        
        # Analyze impulse buying
        if "impulse_buying" in patterns:
            impulse_savings = self._calculate_impulse_savings(spending_data)
            suggestions.append(f"Implement 24-hour rule for non-essential purchases - save ${impulse_savings:.2f}/month")
            total_potential_savings += impulse_savings
        
        # Analyze transportation costs
        transport_savings = self._calculate_transport_savings(spending_data)
        if transport_savings > 0:
            suggestions.append(f"Optimize transportation through carpooling/public transit - save ${transport_savings:.2f}/month")
            total_potential_savings += transport_savings
        
        # Analyze small purchases
        if "frequent_small_purchases" in patterns:
            small_purchase_savings = self._calculate_small_purchase_savings(spending_data)
            suggestions.append(f"Reduce small impulse purchases by 40% - save ${small_purchase_savings:.2f}/month")
            total_potential_savings += small_purchase_savings
        
        difficulty_level = self._assess_difficulty_level(suggestions)
        impact_score = min(10.0, (total_potential_savings / 100) * 2)  # Scale impact
        
        implementation_tips = [
            "Start with the easiest changes first to build momentum",
            "Track your progress weekly using the app",
            "Set up automatic transfers for saved amounts",
            "Reward yourself for meeting monthly savings goals"
        ]
        
        return {
            "potential_savings": round(total_potential_savings, 2),
            "suggestions": suggestions[:4],  # Top 4 suggestions
            "difficulty_level": difficulty_level,
            "impact_score": round(impact_score, 1),
            "implementation_tips": implementation_tips
        }
    
    def _calculate_subscription_savings(self, spending_data: List[Dict]) -> float:
        """Calculate potential savings from subscription optimization"""
        subscription_expenses = []
        
        for expense in spending_data:
            description = expense['description'].lower()
            if any(word in description for word in ['subscription', 'monthly', 'netflix', 'spotify', 'gym']):
                subscription_expenses.append(expense['amount'])
        
        if not subscription_expenses:
            return 0.0
        
        # Calculate tier-appropriate subscription optimization potential
        user_context = self._get_user_context()
        tier = classify_income(user_context.monthly_income)
        
        # Higher income tiers typically have more subscriptions to optimize
        optimization_rates = {
            'low': 0.2,           # 20% - fewer subscriptions
            'lower_middle': 0.25, # 25%
            'middle': 0.3,        # 30%
            'upper_middle': 0.35, # 35% - more subscription services
            'high': 0.4           # 40% - many premium subscriptions
        }
        
        optimization_rate = optimization_rates.get(tier.value, 0.3)
        monthly_subscription_cost = sum(subscription_expenses) / max(1, len(set(expense['date'].strftime('%Y-%m') for expense in spending_data)))
        return monthly_subscription_cost * optimization_rate
    
    def _calculate_dining_savings(self, spending_data: List[Dict]) -> float:
        """Calculate potential savings from dining optimization"""
        dining_expenses = [
            expense for expense in spending_data 
            if 'dining' in expense['category'].lower() or 'restaurant' in expense['category'].lower()
        ]
        
        if not dining_expenses:
            return 0.0
        
        monthly_dining = sum(expense['amount'] for expense in dining_expenses) / max(1, len(set(expense['date'].strftime('%Y-%m') for expense in spending_data)))
        
        # Calculate income-appropriate dining reduction potential
        user_context = self._get_user_context()
        tier = classify_income(user_context.monthly_income)
        
        # Higher income tiers have more dining flexibility but less percentage impact
        reduction_rates = {
            'low': 0.15,          # 15% - limited dining to cut
            'lower_middle': 0.20, # 20%
            'middle': 0.25,       # 25%
            'upper_middle': 0.30, # 30% - more dining flexibility
            'high': 0.20          # 20% - dining is lifestyle choice
        }
        
        reduction_rate = reduction_rates.get(tier.value, 0.25)
        return monthly_dining * reduction_rate
    
    def _calculate_impulse_savings(self, spending_data: List[Dict]) -> float:
        """Calculate potential savings from impulse buying reduction"""
        impulse_score = self._detect_impulse_buying(spending_data)
        total_monthly_spending = sum(expense['amount'] for expense in spending_data) / max(1, len(set(expense['date'].strftime('%Y-%m') for expense in spending_data)))
        
        # Impulse purchases typically represent portion of entertainment/shopping
        estimated_impulse_spending = total_monthly_spending * impulse_score * 0.3
        
        # Calculate tier-appropriate impulse reduction potential
        user_context = self._get_user_context()
        tier = classify_income(user_context.monthly_income)
        
        # Lower income tiers should target higher reduction rates
        reduction_rates = {
            'low': 0.6,           # 60% - impulse buying more problematic
            'lower_middle': 0.55, # 55%
            'middle': 0.5,        # 50%
            'upper_middle': 0.4,  # 40% - some impulse buying acceptable
            'high': 0.3           # 30% - impulse buying less concerning
        }
        
        reduction_rate = reduction_rates.get(tier.value, 0.5)
        return estimated_impulse_spending * reduction_rate
    
    def _calculate_transport_savings(self, spending_data: List[Dict]) -> float:
        """Calculate potential transportation savings"""
        transport_expenses = [
            expense for expense in spending_data 
            if any(word in expense['category'].lower() for word in ['transport', 'gas', 'fuel', 'uber', 'taxi'])
        ]
        
        if not transport_expenses:
            return 0.0
        
        monthly_transport = sum(expense['amount'] for expense in transport_expenses) / max(1, len(set(expense['date'].strftime('%Y-%m') for expense in spending_data)))
        
        # Calculate region and tier-appropriate transport savings
        user_context = self._get_user_context()
        tier = classify_income(user_context.monthly_income)
        
        # Urban areas and lower income tiers have more optimization potential
        base_reduction = 0.2  # 20% baseline
        
        # Adjust for income tier
        tier_adjustments = {
            'low': 1.2,           # More potential savings
            'lower_middle': 1.1,
            'middle': 1.0,
            'upper_middle': 0.9,  # Less potential (premium options chosen)
            'high': 0.8           # Limited potential (efficiency already optimized)
        }
        
        tier_multiplier = tier_adjustments.get(tier.value, 1.0)
        reduction_rate = base_reduction * tier_multiplier
        
        return monthly_transport * min(0.3, reduction_rate)
    
    def _calculate_small_purchase_savings(self, spending_data: List[Dict]) -> float:
        """Calculate savings from reducing small purchases"""
        small_purchases = [expense for expense in spending_data if expense['amount'] < 25]
        
        if not small_purchases:
            return 0.0
        
        monthly_small_purchases = sum(expense['amount'] for expense in small_purchases) / max(1, len(set(expense['date'].strftime('%Y-%m') for expense in spending_data)))
        
        # Calculate tier-appropriate small purchase reduction
        user_context = self._get_user_context()
        tier = classify_income(user_context.monthly_income)
        
        # Lower income tiers should target higher reduction rates for small purchases
        reduction_rates = {
            'low': 0.5,           # 50% - small purchases more impactful
            'lower_middle': 0.45, # 45%
            'middle': 0.4,        # 40%
            'upper_middle': 0.35, # 35%
            'high': 0.25          # 25% - small purchases less significant
        }
        
        reduction_rate = reduction_rates.get(tier.value, 0.4)
        return monthly_small_purchases * reduction_rate
    
    def _assess_difficulty_level(self, suggestions: List[str]) -> str:
        """Assess overall difficulty of implementing suggestions"""
        if len(suggestions) <= 2:
            return "easy"
        elif len(suggestions) <= 4:
            return "moderate"
        else:
            return "challenging"
    
    def generate_weekly_insights(self) -> Dict:
        """Generate weekly AI insights with trend analysis"""
        spending_data = self._load_spending_data(months_back=2)  # Focus on recent data
        
        if not spending_data:
            return {
                "insights": "Start tracking expenses to receive weekly insights.",
                "trend": "stable",
                "weekly_summary": {},
                "recommendations": []
            }
        
        # Get current and previous week data
        now = datetime.utcnow()
        current_week_start = now - timedelta(days=now.weekday())
        previous_week_start = current_week_start - timedelta(days=7)
        
        current_week_data = [
            expense for expense in spending_data
            if expense['date'] >= current_week_start
        ]
        
        previous_week_data = [
            expense for expense in spending_data
            if previous_week_start <= expense['date'] < current_week_start
        ]
        
        # Calculate weekly metrics
        current_total = sum(expense['amount'] for expense in current_week_data)
        previous_total = sum(expense['amount'] for expense in previous_week_data)
        
        # Calculate percentage change
        if previous_total > 0:
            percentage_change = ((current_total - previous_total) / previous_total) * 100
        else:
            percentage_change = 0
        
        # Determine trend
        if percentage_change > 10:
            trend = "increasing"
        elif percentage_change < -10:
            trend = "decreasing"
        else:
            trend = "stable"
        
        # Find top category this week
        category_totals = {}
        for expense in current_week_data:
            category = expense['category']
            category_totals[category] = category_totals.get(category, 0) + expense['amount']
        
        top_category = max(category_totals.items(), key=lambda x: x[1])[0] if category_totals else "general"
        
        # Find biggest single expense
        biggest_expense = max(current_week_data, key=lambda x: x['amount'])['amount'] if current_week_data else 0
        
        # Generate insights text
        insights_text = self._generate_weekly_insights_text(
            current_total, previous_total, percentage_change, top_category, trend
        )
        
        # Generate recommendations
        recommendations = self._generate_weekly_recommendations(
            current_week_data, trend, percentage_change
        )
        
        weekly_summary = {
            "total_spent": round(current_total, 2),
            "vs_last_week": round(percentage_change, 1),
            "top_category": top_category,
            "biggest_expense": round(biggest_expense, 2),
            "transaction_count": len(current_week_data)
        }
        
        return {
            "insights": insights_text,
            "trend": trend,
            "weekly_summary": weekly_summary,
            "recommendations": recommendations[:3]
        }
    
    def _generate_weekly_insights_text(self, current_total: float, previous_total: float, 
                                     percentage_change: float, top_category: str, trend: str) -> str:
        """Generate weekly insights text"""
        if previous_total == 0:
            return f"This week you spent ${current_total:.2f}. Your largest expense category was {top_category}."
        
        change_text = "increased" if percentage_change > 0 else "decreased"
        abs_change = abs(percentage_change)
        
        base_text = f"This week you spent ${current_total:.2f}, which {change_text} by {abs_change:.1f}% compared to last week."
        
        if trend == "decreasing":
            sentiment = "Great progress toward your budget goals!"
        elif trend == "increasing":
            sentiment = "Consider reviewing your spending patterns."
        else:
            sentiment = "Your spending remains consistent."
        
        return f"{base_text} {sentiment} Your largest expense category was {top_category}."
    
    def _generate_weekly_recommendations(self, current_week_data: List[Dict], 
                                       trend: str, percentage_change: float) -> List[str]:
        """Generate weekly recommendations"""
        recommendations = []
        
        if trend == "increasing":
            recommendations.append("Consider reducing discretionary spending for the remainder of the month")
            recommendations.append("Review your largest expense categories for optimization opportunities")
        elif trend == "decreasing":
            recommendations.append("Excellent progress! Consider putting the savings toward your emergency fund")
            recommendations.append("Continue current spending patterns - they're working well")
        else:
            recommendations.append("Maintain your current spending discipline")
            recommendations.append("Look for small optimization opportunities to improve further")
        
        # Category-specific recommendations
        if current_week_data:
            top_category = max(
                set(expense['category'] for expense in current_week_data),
                key=lambda cat: sum(exp['amount'] for exp in current_week_data if exp['category'] == cat)
            )
            
            if top_category.lower() in ['dining', 'food']:
                recommendations.append("Try meal prep this weekend to reduce food costs next week")
            elif top_category.lower() in ['entertainment', 'shopping']:
                recommendations.append("Set a specific entertainment budget for next week and track it daily")
        
        return recommendations