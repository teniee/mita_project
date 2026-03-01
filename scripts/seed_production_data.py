#!/usr/bin/env python3
"""
MITA Finance Production Data Seeding Script
Seeds essential data for production deployment
"""

import os
import sys
import asyncio
import logging

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Import your models
from app.db.models.ai_advice_template import AIAdviceTemplate
from app.db.models.budget_advice import BudgetAdvice

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProductionDataSeeder:
    """Seeds essential data for MITA Finance production environment"""
    
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        # Create async engine
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={
                "statement_cache_size": 0,  # CRITICAL: Disable for PgBouncer
                "prepared_statement_cache_size": 0,  # CRITICAL: Disable for PgBouncer
                "server_settings": {"jit": "off"}
            }
        )
        
        # Create session factory
        self.async_session = sessionmaker(
            self.engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
    
    async def create_ai_advice_templates(self, session: AsyncSession):
        """Create AI advice templates for different financial scenarios"""
        logger.info("Creating AI advice templates...")
        
        templates = [
            {
                "category": "budgeting",
                "subcategory": "overspending",
                "template": "You've spent {amount} over your {category} budget this month. Consider reducing discretionary expenses or reallocating from other categories.",
                "priority": "high",
                "is_active": True
            },
            {
                "category": "savings",
                "subcategory": "emergency_fund",
                "template": "Great job saving {amount} this month! You're {percentage}% closer to your emergency fund goal of {target_amount}.",
                "priority": "medium",
                "is_active": True
            },
            {
                "category": "spending",
                "subcategory": "unusual_pattern",
                "template": "I noticed your {category} spending increased by {percentage}% compared to last month. This might be worth reviewing.",
                "priority": "medium",
                "is_active": True
            },
            {
                "category": "income",
                "subcategory": "irregular",
                "template": "Your income varies month to month. Consider setting aside {percentage}% of higher-income months for stability.",
                "priority": "high",
                "is_active": True
            },
            {
                "category": "goals",
                "subcategory": "progress",
                "template": "You're making excellent progress on your {goal_name}! At this rate, you'll reach your goal by {estimated_date}.",
                "priority": "low",
                "is_active": True
            },
            {
                "category": "bills",
                "subcategory": "due_soon",
                "template": "Your {service_name} bill of {amount} is due in {days} days. Make sure you have sufficient funds available.",
                "priority": "high",
                "is_active": True
            },
            {
                "category": "investment",
                "subcategory": "opportunity",
                "template": "With your current savings rate, you could invest {amount} monthly. Consider low-cost index funds for long-term growth.",
                "priority": "medium",
                "is_active": True
            },
            {
                "category": "debt",
                "subcategory": "payoff_strategy",
                "template": "Focus on paying off your {debt_type} first - it has the highest interest rate at {rate}%. This could save you {savings} in interest.",
                "priority": "high",
                "is_active": True
            }
        ]
        
        created_count = 0
        for template_data in templates:
            # Check if template already exists
            existing = await session.execute(
                text("SELECT id FROM ai_advice_templates WHERE category = :category AND subcategory = :subcategory"),
                {"category": template_data["category"], "subcategory": template_data["subcategory"]}
            )
            
            if not existing.first():
                template = AIAdviceTemplate(**template_data)
                session.add(template)
                created_count += 1
        
        await session.commit()
        logger.info(f"Created {created_count} AI advice templates")
    
    async def create_budget_advice_categories(self, session: AsyncSession):
        """Create default budget advice categories"""
        logger.info("Creating budget advice categories...")
        
        categories = [
            {
                "category": "housing",
                "advice_text": "Housing should typically be 25-30% of your income. Consider downsizing if it's significantly higher.",
                "percentage_min": 25,
                "percentage_max": 30,
                "priority": "high"
            },
            {
                "category": "transportation",
                "advice_text": "Transportation costs should be 10-15% of income. Consider public transport or carpooling to reduce expenses.",
                "percentage_min": 10,
                "percentage_max": 15,
                "priority": "medium"
            },
            {
                "category": "food",
                "advice_text": "Food expenses should be 10-15% of income. Meal planning and cooking at home can help reduce costs.",
                "percentage_min": 10,
                "percentage_max": 15,
                "priority": "medium"
            },
            {
                "category": "utilities",
                "advice_text": "Utilities should be 5-10% of income. Energy-efficient appliances and mindful usage can lower bills.",
                "percentage_min": 5,
                "percentage_max": 10,
                "priority": "low"
            },
            {
                "category": "entertainment",
                "advice_text": "Entertainment should be 5-10% of income. Look for free activities and limit subscription services.",
                "percentage_min": 5,
                "percentage_max": 10,
                "priority": "low"
            },
            {
                "category": "savings",
                "advice_text": "Aim to save at least 20% of your income. Start with an emergency fund covering 3-6 months of expenses.",
                "percentage_min": 20,
                "percentage_max": 30,
                "priority": "high"
            }
        ]
        
        created_count = 0
        for category_data in categories:
            # Check if category already exists
            existing = await session.execute(
                text("SELECT id FROM budget_advice WHERE category = :category"),
                {"category": category_data["category"]}
            )
            
            if not existing.first():
                budget_advice = BudgetAdvice(**category_data)
                session.add(budget_advice)
                created_count += 1
        
        await session.commit()
        logger.info(f"Created {created_count} budget advice categories")
    
    async def create_system_indexes(self, session: AsyncSession):
        """Create production-optimized database indexes"""
        logger.info("Creating production database indexes...")
        
        indexes = [
            # User indexes
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_lower ON users (LOWER(email))",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_created_at ON users (created_at)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_is_premium ON users (is_premium)",
            
            # Transaction indexes
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_id_date ON transactions (user_id, created_at DESC)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_category ON transactions (category)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_amount ON transactions (amount)",
            
            # Goal indexes
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_goals_user_id_active ON goals (user_id, is_active)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_goals_target_date ON goals (target_date)",
            
            # Expense indexes
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_user_id_date ON expenses (user_id, created_at DESC)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_category ON expenses (category)",
            
            # Notification indexes
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_logs_user_id ON notification_logs (user_id)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_logs_sent_at ON notification_logs (sent_at)",
            
            # Mood indexes
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_moods_user_id_date ON moods (user_id, created_at DESC)",
            
            # Push token indexes
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_push_tokens_user_id ON push_tokens (user_id)",
            
            # Performance monitoring indexes
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_analysis_snapshots_user_id ON ai_analysis_snapshots (user_id)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_analysis_snapshots_created_at ON ai_analysis_snapshots (created_at)"
        ]
        
        created_count = 0
        for index_sql in indexes:
            try:
                await session.execute(text(index_sql))
                created_count += 1
                logger.info(f"Created index: {index_sql.split('idx_')[1].split(' ')[0] if 'idx_' in index_sql else 'unknown'}")
            except Exception as e:
                logger.warning(f"Index creation failed (may already exist): {str(e)}")
        
        await session.commit()
        logger.info(f"Processed {created_count} database indexes")
    
    async def verify_database_connection(self):
        """Verify database connection and basic functionality"""
        logger.info("Verifying database connection...")
        
        try:
            async with self.async_session() as session:
                result = await session.execute(text("SELECT version()"))
                version = result.scalar()
                logger.info(f"Connected to PostgreSQL: {version}")
                
                # Check if all required tables exist
                tables_check = await session.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('users', 'transactions', 'goals', 'expenses')
                """))
                
                existing_tables = [row[0] for row in tables_check.fetchall()]
                required_tables = ['users', 'transactions', 'goals', 'expenses']
                missing_tables = set(required_tables) - set(existing_tables)
                
                if missing_tables:
                    logger.error(f"Missing required tables: {missing_tables}")
                    return False
                
                logger.info("All required tables exist")
                return True
                
        except Exception as e:
            logger.error(f"Database connection verification failed: {str(e)}")
            return False
    
    async def seed_all_data(self):
        """Execute all seeding operations"""
        logger.info("Starting production data seeding for MITA Finance...")
        
        try:
            # Verify database connection
            if not await self.verify_database_connection():
                logger.error("Database verification failed")
                return False
            
            async with self.async_session() as session:
                # Create AI advice templates
                await self.create_ai_advice_templates(session)
                
                # Create budget advice categories
                await self.create_budget_advice_categories(session)
                
                # Create performance indexes
                await self.create_system_indexes(session)
            
            logger.info("✅ Production data seeding completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Production data seeding failed: {str(e)}")
            return False
        finally:
            await self.engine.dispose()


async def main():
    """Main seeding execution"""
    try:
        seeder = ProductionDataSeeder()
        success = await seeder.seed_all_data()
        
        if success:
            logger.info("Production data seeding completed successfully")
            sys.exit(0)
        else:
            logger.error("Production data seeding failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error in data seeding: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())