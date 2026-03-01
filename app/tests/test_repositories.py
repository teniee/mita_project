"""
Comprehensive tests for repository pattern implementation
Tests all repositories: Base, User, Transaction, Expense, and Goal
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from app.repositories.user_repository import get_user_repository
from app.repositories.transaction_repository import get_transaction_repository
from app.repositories.expense_repository import get_expense_repository
from app.repositories.goal_repository import get_goal_repository


class TestBaseRepository:
    """Test the base repository functionality"""
    
    @pytest.fixture
    async def user_repo(self):
        return get_user_repository()
    
    @pytest.mark.asyncio
    async def test_create_and_get_by_id(self, user_repo):
        """Test basic create and retrieve operations"""
        user_data = {
            'email': 'test@example.com',
            'password_hash': 'hashed_password',
            'country': 'US',
            'is_premium': False
        }
        
        # Create user
        user = await user_repo.create(user_data)
        assert user is not None
        assert user.email == 'test@example.com'
        assert user.country == 'US'
        
        # Retrieve by ID
        retrieved_user = await user_repo.get_by_id(user.id)
        assert retrieved_user is not None
        assert retrieved_user.email == user.email
    
    @pytest.mark.asyncio
    async def test_update_and_delete(self, user_repo):
        """Test update and delete operations"""
        user_data = {
            'email': 'update_test@example.com',
            'password_hash': 'hashed_password',
            'country': 'US'
        }
        
        # Create user
        user = await user_repo.create(user_data)
        original_id = user.id
        
        # Update user
        updated_user = await user_repo.update(user.id, {'country': 'CA', 'is_premium': True})
        assert updated_user is not None
        assert updated_user.id == original_id
        assert updated_user.country == 'CA'
        assert updated_user.is_premium is True
        
        # Delete user
        deleted = await user_repo.delete(user.id)
        assert deleted is True
        
        # Verify deletion
        retrieved_user = await user_repo.get_by_id(user.id)
        assert retrieved_user is None
    
    @pytest.mark.asyncio
    async def test_get_multi_with_filters(self, user_repo):
        """Test retrieving multiple records with filters"""
        # Create test users
        users_data = [
            {'email': 'premium1@example.com', 'password_hash': 'hash1', 'is_premium': True},
            {'email': 'premium2@example.com', 'password_hash': 'hash2', 'is_premium': True},
            {'email': 'regular@example.com', 'password_hash': 'hash3', 'is_premium': False},
        ]
        
        created_users = []
        for user_data in users_data:
            user = await user_repo.create(user_data)
            created_users.append(user)
        
        # Test filtering
        premium_users = await user_repo.get_multi(filters={'is_premium': True})
        assert len(premium_users) >= 2
        
        # Test pagination
        limited_users = await user_repo.get_multi(limit=1)
        assert len(limited_users) == 1
        
        # Cleanup
        for user in created_users:
            await user_repo.delete(user.id)


class TestUserRepository:
    """Test user-specific repository operations"""
    
    @pytest.fixture
    async def user_repo(self):
        return get_user_repository()
    
    @pytest.mark.asyncio
    async def test_get_by_email(self, user_repo):
        """Test getting user by email"""
        user_data = {
            'email': 'email_test@example.com',
            'password_hash': 'hashed_password'
        }
        
        # Create user
        user = await user_repo.create_user(user_data)
        
        # Retrieve by email
        retrieved_user = await user_repo.get_by_email('email_test@example.com')
        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        
        # Test case insensitive
        retrieved_user_caps = await user_repo.get_by_email('EMAIL_TEST@EXAMPLE.COM')
        assert retrieved_user_caps is not None
        assert retrieved_user_caps.id == user.id
        
        # Cleanup
        await user_repo.delete(user.id)
    
    @pytest.mark.asyncio
    async def test_create_user_email_normalization(self, user_repo):
        """Test email normalization during user creation"""
        user_data = {
            'email': 'UPPERCASE@EXAMPLE.COM',
            'password_hash': 'hashed_password'
        }
        
        user = await user_repo.create_user(user_data)
        assert user.email == 'uppercase@example.com'
        
        # Cleanup
        await user_repo.delete(user.id)
    
    @pytest.mark.asyncio
    async def test_update_last_login(self, user_repo):
        """Test updating last login timestamp"""
        user_data = {
            'email': 'login_test@example.com',
            'password_hash': 'hashed_password'
        }
        
        user = await user_repo.create_user(user_data)
        original_login = user.last_login
        
        # Update last login
        updated = await user_repo.update_last_login(user.id)
        assert updated is True
        
        # Verify update
        updated_user = await user_repo.get_by_id(user.id)
        assert updated_user.last_login != original_login
        assert updated_user.last_login is not None
        
        # Cleanup
        await user_repo.delete(user.id)
    
    @pytest.mark.asyncio
    async def test_get_premium_users(self, user_repo):
        """Test getting premium users"""
        # Create premium and regular users
        premium_user_data = {
            'email': 'premium_test@example.com',
            'password_hash': 'hash',
            'is_premium': True
        }
        regular_user_data = {
            'email': 'regular_test@example.com',
            'password_hash': 'hash',
            'is_premium': False
        }
        
        premium_user = await user_repo.create_user(premium_user_data)
        regular_user = await user_repo.create_user(regular_user_data)
        
        # Get premium users
        premium_users = await user_repo.get_premium_users()
        premium_user_ids = [u.id for u in premium_users]
        
        assert premium_user.id in premium_user_ids
        assert regular_user.id not in premium_user_ids
        
        # Cleanup
        await user_repo.delete(premium_user.id)
        await user_repo.delete(regular_user.id)
    
    @pytest.mark.asyncio
    async def test_get_user_stats(self, user_repo):
        """Test comprehensive user statistics"""
        # Create test users
        user_data = {
            'email': 'stats_test@example.com',
            'password_hash': 'hash',
            'is_premium': True
        }
        
        user = await user_repo.create_user(user_data)
        
        # Get stats
        stats = await user_repo.get_user_stats()
        
        assert 'total_users' in stats
        assert 'premium_users' in stats
        assert 'premium_rate' in stats
        assert stats['total_users'] >= 1
        assert stats['premium_rate'] >= 0
        
        # Cleanup
        await user_repo.delete(user.id)


class TestTransactionRepository:
    """Test transaction repository operations"""
    
    @pytest.fixture
    async def transaction_repo(self):
        return get_transaction_repository()
    
    @pytest.fixture
    async def user_repo(self):
        return get_user_repository()
    
    @pytest.fixture
    async def test_user(self, user_repo):
        """Create a test user for transaction tests"""
        user_data = {
            'email': 'transaction_test@example.com',
            'password_hash': 'hash'
        }
        user = await user_repo.create_user(user_data)
        yield user
        # Cleanup
        await user_repo.delete(user.id)
    
    @pytest.mark.asyncio
    async def test_get_by_user(self, transaction_repo, test_user):
        """Test getting transactions by user"""
        # Create test transactions
        transaction_data = [
            {
                'user_id': test_user.id,
                'category': 'Food',
                'amount': Decimal('25.50'),
                'transaction_type': 'expense'
            },
            {
                'user_id': test_user.id,
                'category': 'Transport',
                'amount': Decimal('15.00'),
                'transaction_type': 'expense'
            }
        ]
        
        created_transactions = []
        for data in transaction_data:
            transaction = await transaction_repo.create(data)
            created_transactions.append(transaction)
        
        # Get user's transactions
        user_transactions = await transaction_repo.get_by_user(test_user.id)
        
        assert len(user_transactions) >= 2
        user_transaction_ids = [t.id for t in user_transactions]
        
        for transaction in created_transactions:
            assert transaction.id in user_transaction_ids
        
        # Cleanup
        for transaction in created_transactions:
            await transaction_repo.delete(transaction.id)
    
    @pytest.mark.asyncio
    async def test_get_by_category(self, transaction_repo, test_user):
        """Test getting transactions by category"""
        # Create transactions in different categories
        food_transaction = await transaction_repo.create({
            'user_id': test_user.id,
            'category': 'Food',
            'amount': Decimal('30.00'),
            'transaction_type': 'expense'
        })
        
        transport_transaction = await transaction_repo.create({
            'user_id': test_user.id,
            'category': 'Transport',
            'amount': Decimal('20.00'),
            'transaction_type': 'expense'
        })
        
        # Get food transactions
        food_transactions = await transaction_repo.get_by_category(test_user.id, 'Food')
        food_transaction_ids = [t.id for t in food_transactions]
        
        assert food_transaction.id in food_transaction_ids
        assert transport_transaction.id not in food_transaction_ids
        
        # Cleanup
        await transaction_repo.delete(food_transaction.id)
        await transaction_repo.delete(transport_transaction.id)
    
    @pytest.mark.asyncio
    async def test_get_total_spent_by_period(self, transaction_repo, test_user):
        """Test calculating total spent in a period"""
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        
        # Create transactions
        transaction1 = await transaction_repo.create({
            'user_id': test_user.id,
            'category': 'Food',
            'amount': Decimal('25.50'),
            'transaction_type': 'expense',
            'spent_at': now
        })
        
        transaction2 = await transaction_repo.create({
            'user_id': test_user.id,
            'category': 'Transport',
            'amount': Decimal('15.00'),
            'transaction_type': 'expense',
            'spent_at': now
        })
        
        # Calculate total
        total = await transaction_repo.get_total_spent_by_period(
            test_user.id, yesterday, now + timedelta(hours=1)
        )
        
        assert total >= Decimal('40.50')
        
        # Cleanup
        await transaction_repo.delete(transaction1.id)
        await transaction_repo.delete(transaction2.id)


class TestExpenseRepository:
    """Test expense repository operations"""
    
    @pytest.fixture
    async def expense_repo(self):
        return get_expense_repository()
    
    @pytest.fixture
    async def user_repo(self):
        return get_user_repository()
    
    @pytest.fixture
    async def test_user(self, user_repo):
        """Create a test user for expense tests"""
        user_data = {
            'email': 'expense_test@example.com',
            'password_hash': 'hash'
        }
        user = await user_repo.create_user(user_data)
        yield user
        await user_repo.delete(user.id)
    
    @pytest.mark.asyncio
    async def test_get_daily_total(self, expense_repo, test_user):
        """Test calculating daily expense total"""
        today = datetime.now()
        
        # Create expenses for today
        expense1 = await expense_repo.create({
            'user_id': str(test_user.id),  # Expense model uses String user_id
            'action': 'groceries',
            'amount': 45.75,
            'date': today.date()
        })
        
        expense2 = await expense_repo.create({
            'user_id': str(test_user.id),
            'action': 'coffee',
            'amount': 4.25,
            'date': today.date()
        })
        
        # Calculate daily total
        total = await expense_repo.get_daily_total(str(test_user.id), today)
        
        assert total >= Decimal('50.00')
        
        # Cleanup
        await expense_repo.delete(expense1.id)
        await expense_repo.delete(expense2.id)
    
    @pytest.mark.asyncio
    async def test_get_by_date_range(self, expense_repo, test_user):
        """Test getting expenses by date range"""
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        
        # Create expense for today
        expense = await expense_repo.create({
            'user_id': str(test_user.id),
            'action': 'lunch',
            'amount': 12.50,
            'date': today.date()
        })
        
        # Get expenses in range
        expenses = await expense_repo.get_by_date_range(
            str(test_user.id), yesterday, tomorrow
        )
        
        expense_ids = [e.id for e in expenses]
        assert expense.id in expense_ids
        
        # Cleanup
        await expense_repo.delete(expense.id)


class TestGoalRepository:
    """Test goal repository operations"""
    
    @pytest.fixture
    async def goal_repo(self):
        return get_goal_repository()
    
    @pytest.fixture
    async def user_repo(self):
        return get_user_repository()
    
    @pytest.fixture
    async def test_user(self, user_repo):
        """Create a test user for goal tests"""
        user_data = {
            'email': 'goal_test@example.com',
            'password_hash': 'hash'
        }
        user = await user_repo.create_user(user_data)
        yield user
        await user_repo.delete(user.id)
    
    @pytest.mark.asyncio
    async def test_get_active_goals(self, goal_repo, test_user):
        """Test getting active goals"""
        # Create active and completed goals
        active_goal = await goal_repo.create({
            'user_id': test_user.id,
            'title': 'Save $1000',
            'description': 'Emergency fund',
            'category': 'savings',
            'status': 'active',
            'progress': 50.0,
            'target_date': (datetime.now() + timedelta(days=30)).date()
        })
        
        completed_goal = await goal_repo.create({
            'user_id': test_user.id,
            'title': 'Save $500',
            'description': 'Vacation fund',
            'category': 'savings',
            'status': 'completed',
            'progress': 100.0,
            'target_date': datetime.now().date()
        })
        
        # Get active goals
        active_goals = await goal_repo.get_active_goals(test_user.id)
        active_goal_ids = [g.id for g in active_goals]
        
        assert active_goal.id in active_goal_ids
        assert completed_goal.id not in active_goal_ids
        
        # Cleanup
        await goal_repo.delete(active_goal.id)
        await goal_repo.delete(completed_goal.id)
    
    @pytest.mark.asyncio
    async def test_update_goal_progress(self, goal_repo, test_user):
        """Test updating goal progress"""
        goal = await goal_repo.create({
            'user_id': test_user.id,
            'title': 'Test Goal',
            'description': 'Progress test',
            'category': 'savings',
            'status': 'active',
            'progress': 25.0,
            'target_date': (datetime.now() + timedelta(days=30)).date()
        })
        
        # Update progress
        updated = await goal_repo.update_goal_progress(goal.id, 75.0)
        assert updated is True
        
        # Verify update
        updated_goal = await goal_repo.get_by_id(goal.id)
        assert updated_goal.progress == 75.0
        
        # Test completion (100% progress)
        completed = await goal_repo.update_goal_progress(goal.id, 100.0)
        assert completed is True
        
        completed_goal = await goal_repo.get_by_id(goal.id)
        assert completed_goal.progress == 100.0
        assert completed_goal.status == 'completed'
        assert completed_goal.completed_at is not None
        
        # Cleanup
        await goal_repo.delete(goal.id)
    
    @pytest.mark.asyncio
    async def test_get_goals_due_soon(self, goal_repo, test_user):
        """Test getting goals due soon"""
        today = datetime.now().date()
        
        # Create goal due in 5 days
        due_soon_goal = await goal_repo.create({
            'user_id': test_user.id,
            'title': 'Due Soon Goal',
            'description': 'Test',
            'category': 'savings',
            'status': 'active',
            'progress': 50.0,
            'target_date': today + timedelta(days=5)
        })
        
        # Create goal due in 30 days
        future_goal = await goal_repo.create({
            'user_id': test_user.id,
            'title': 'Future Goal',
            'description': 'Test',
            'category': 'savings',
            'status': 'active',
            'progress': 10.0,
            'target_date': today + timedelta(days=30)
        })
        
        # Get goals due within 7 days
        due_soon = await goal_repo.get_goals_due_soon(test_user.id, 7)
        due_soon_ids = [g.id for g in due_soon]
        
        assert due_soon_goal.id in due_soon_ids
        assert future_goal.id not in due_soon_ids
        
        # Cleanup
        await goal_repo.delete(due_soon_goal.id)
        await goal_repo.delete(future_goal.id)
    
    @pytest.mark.asyncio
    async def test_get_goal_statistics(self, goal_repo, test_user):
        """Test comprehensive goal statistics"""
        # Create various goals
        active_goal = await goal_repo.create({
            'user_id': test_user.id,
            'title': 'Active Test',
            'category': 'savings',
            'status': 'active',
            'progress': 50.0,
            'target_date': (datetime.now() + timedelta(days=30)).date()
        })
        
        completed_goal = await goal_repo.create({
            'user_id': test_user.id,
            'title': 'Completed Test',
            'category': 'fitness',
            'status': 'completed',
            'progress': 100.0,
            'completed_at': datetime.now(),
            'target_date': datetime.now().date()
        })
        
        # Get statistics
        stats = await goal_repo.get_goal_statistics(test_user.id)
        
        assert 'total_goals' in stats
        assert 'active_goals' in stats
        assert 'completed_goals' in stats
        assert 'completion_rate' in stats
        assert 'average_progress' in stats
        assert 'goals_by_category' in stats
        
        assert stats['total_goals'] >= 2
        assert stats['active_goals'] >= 1
        assert stats['completed_goals'] >= 1
        assert stats['completion_rate'] > 0
        
        # Cleanup
        await goal_repo.delete(active_goal.id)
        await goal_repo.delete(completed_goal.id)