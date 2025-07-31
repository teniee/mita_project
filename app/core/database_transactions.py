"""
Database Transaction Management System
Provides robust transaction handling with automatic rollback and retry logic
"""

import logging
import asyncio
from typing import Any, Callable, Optional, Dict, List
from contextlib import asynccontextmanager
from functools import wraps
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import (
    SQLAlchemyError, 
    IntegrityError, 
    OperationalError,
    TimeoutError as SQLTimeoutError,
    DisconnectionError
)
from sqlalchemy import text

from app.core.async_session import get_async_db_context
from app.core.error_monitoring import log_error, ErrorSeverity, ErrorCategory

logger = logging.getLogger(__name__)


class TransactionError(Exception):
    """Custom transaction error"""
    def __init__(self, message: str, original_error: Exception = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


class TransactionManager:
    """Manages database transactions with retry logic and rollback handling"""
    
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 0.5  # seconds
        self.deadlock_retry_delay = 1.0  # seconds
        
        # Retryable error types
        self.retryable_errors = (
            OperationalError,
            SQLTimeoutError,
            DisconnectionError,
        )
    
    @asynccontextmanager
    async def transaction(
        self, 
        session: AsyncSession = None,
        savepoint: bool = False,
        retry_on_failure: bool = True
    ):
        """
        Context manager for database transactions with automatic rollback
        
        Args:
            session: Optional existing session to use
            savepoint: Use savepoint instead of full transaction
            retry_on_failure: Whether to retry on retryable errors
        """
        if session:
            # Use existing session
            if savepoint:
                async with session.begin_nested() as transaction:
                    try:
                        yield session
                        await transaction.commit()
                    except Exception as e:
                        await transaction.rollback()
                        await self._handle_transaction_error(e, "savepoint")
                        raise
            else:
                # Use existing session without nested transaction
                yield session
        else:
            # Create new session
            async with get_async_db_context() as db_session:
                transaction = await db_session.begin()
                try:
                    yield db_session
                    await transaction.commit()
                except Exception as e:
                    await transaction.rollback()
                    await self._handle_transaction_error(e, "transaction")
                    raise
    
    async def execute_with_retry(
        self,
        operation: Callable,
        *args,
        max_retries: int = None,
        retry_delay: float = None,
        **kwargs
    ) -> Any:
        """
        Execute database operation with automatic retry on failure
        
        Args:
            operation: The async function to execute
            args: Positional arguments for the operation
            max_retries: Maximum number of retries (overrides default)
            retry_delay: Delay between retries (overrides default)
            kwargs: Keyword arguments for the operation
        """
        max_retries = max_retries or self.max_retries
        retry_delay = retry_delay or self.retry_delay
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                return await operation(*args, **kwargs)
            
            except self.retryable_errors as e:
                last_error = e
                
                if attempt == max_retries:
                    await log_error(
                        e,
                        severity=ErrorSeverity.HIGH,
                        category=ErrorCategory.DATABASE,
                        additional_context={
                            'operation': operation.__name__,
                            'attempt': attempt + 1,
                            'max_retries': max_retries
                        }
                    )
                    raise TransactionError(
                        f"Database operation failed after {max_retries} retries",
                        original_error=e
                    )
                
                # Calculate delay (exponential backoff for deadlocks)
                if "deadlock" in str(e).lower():
                    delay = self.deadlock_retry_delay * (2 ** attempt)
                else:
                    delay = retry_delay * (2 ** attempt)
                
                logger.warning(
                    f"Database operation failed (attempt {attempt + 1}/{max_retries + 1}): {str(e)}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                
                await asyncio.sleep(delay)
                continue
            
            except Exception as e:
                # Non-retryable error
                await log_error(
                    e,
                    severity=ErrorSeverity.HIGH,
                    category=ErrorCategory.DATABASE,
                    additional_context={
                        'operation': operation.__name__,
                        'attempt': attempt + 1,
                        'retryable': False
                    }
                )
                raise TransactionError(
                    f"Database operation failed with non-retryable error",
                    original_error=e
                )
        
        # This should never be reached, but just in case
        raise TransactionError(
            "Unexpected error in retry logic",
            original_error=last_error
        )
    
    async def _handle_transaction_error(self, error: Exception, transaction_type: str):
        """Handle transaction errors with proper logging"""
        severity = ErrorSeverity.HIGH
        
        # Determine severity based on error type
        if isinstance(error, IntegrityError):
            severity = ErrorSeverity.MEDIUM  # Data integrity issues are important but not critical
        elif isinstance(error, (OperationalError, DisconnectionError)):
            severity = ErrorSeverity.HIGH  # Connection issues are serious
        
        await log_error(
            error,
            severity=severity,
            category=ErrorCategory.DATABASE,
            additional_context={
                'transaction_type': transaction_type,
                'error_type': type(error).__name__
            }
        )


class BulkOperationManager:
    """Manages bulk database operations with batching and error handling"""
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.transaction_manager = TransactionManager()
    
    async def bulk_insert(
        self,
        session: AsyncSession,
        model_class: Any,
        data_list: List[Dict[str, Any]],
        ignore_conflicts: bool = False
    ) -> Dict[str, Any]:
        """
        Perform bulk insert with batching and error handling
        
        Args:
            session: Database session
            model_class: SQLAlchemy model class
            data_list: List of data dictionaries to insert
            ignore_conflicts: Whether to ignore duplicate key conflicts
        
        Returns:
            Dictionary with results and statistics
        """
        total_records = len(data_list)
        successful_inserts = 0
        failed_inserts = 0
        errors = []
        
        logger.info(f"Starting bulk insert of {total_records} records for {model_class.__name__}")
        
        # Process in batches
        for i in range(0, total_records, self.batch_size):
            batch = data_list[i:i + self.batch_size]
            batch_number = (i // self.batch_size) + 1
            total_batches = (total_records + self.batch_size - 1) // self.batch_size
            
            try:
                async with self.transaction_manager.transaction(session, savepoint=True):
                    # Create model instances
                    instances = [model_class(**data) for data in batch]
                    
                    # Add to session
                    session.add_all(instances)
                    
                    # Flush to detect conflicts early
                    await session.flush()
                    
                    successful_inserts += len(batch)
                    
                    logger.debug(
                        f"Batch {batch_number}/{total_batches} completed successfully "
                        f"({len(batch)} records)"
                    )
            
            except IntegrityError as e:
                failed_inserts += len(batch)
                error_msg = f"Batch {batch_number} failed with integrity error: {str(e)}"
                errors.append(error_msg)
                
                if not ignore_conflicts:
                    logger.error(error_msg)
                    # Try individual inserts to identify specific failures
                    individual_results = await self._handle_individual_inserts(
                        session, model_class, batch
                    )
                    successful_inserts += individual_results['successful']
                    failed_inserts = failed_inserts - len(batch) + individual_results['failed']
                else:
                    logger.warning(f"Ignoring batch {batch_number} due to conflicts")
            
            except Exception as e:
                failed_inserts += len(batch)
                error_msg = f"Batch {batch_number} failed with error: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
                
                await log_error(
                    e,
                    severity=ErrorSeverity.MEDIUM,
                    category=ErrorCategory.DATABASE,
                    additional_context={
                        'operation': 'bulk_insert',
                        'model': model_class.__name__,
                        'batch_number': batch_number,
                        'batch_size': len(batch)
                    }
                )
        
        result = {
            'total_records': total_records,
            'successful_inserts': successful_inserts,
            'failed_inserts': failed_inserts,
            'success_rate': (successful_inserts / total_records) * 100 if total_records > 0 else 0,
            'errors': errors
        }
        
        logger.info(
            f"Bulk insert completed: {successful_inserts}/{total_records} successful "
            f"({result['success_rate']:.1f}% success rate)"
        )
        
        return result
    
    async def _handle_individual_inserts(
        self,
        session: AsyncSession,
        model_class: Any,
        batch: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Handle individual inserts when batch fails"""
        successful = 0
        failed = 0
        
        for data in batch:
            try:
                async with self.transaction_manager.transaction(session, savepoint=True):
                    instance = model_class(**data)
                    session.add(instance)
                    await session.flush()
                    successful += 1
            except Exception as e:
                failed += 1
                logger.debug(f"Individual insert failed: {str(e)}")
        
        return {'successful': successful, 'failed': failed}


class DatabaseHealthChecker:
    """Checks database health and connection status"""
    
    async def check_database_health(self) -> Dict[str, Any]:
        """Perform comprehensive database health check"""
        health_data = {
            'status': 'unknown',
            'timestamp': None,
            'connection_test': False,
            'query_test': False,
            'transaction_test': False,
            'response_time_ms': None,
            'error': None
        }
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            async with get_async_db_context() as session:
                # Test basic connection
                await session.execute(text('SELECT 1'))
                health_data['connection_test'] = True
                
                # Test simple query
                result = await session.execute(text('SELECT NOW() as current_time'))
                current_time = result.scalar()
                health_data['query_test'] = True
                health_data['timestamp'] = str(current_time)
                
                # Test transaction
                async with session.begin():
                    await session.execute(text('SELECT 1'))
                health_data['transaction_test'] = True
                
                # Calculate response time
                end_time = asyncio.get_event_loop().time()
                health_data['response_time_ms'] = round((end_time - start_time) * 1000, 2)
                
                # Overall status
                if all([health_data['connection_test'], health_data['query_test'], health_data['transaction_test']]):
                    health_data['status'] = 'healthy'
                else:
                    health_data['status'] = 'degraded'
        
        except Exception as e:
            health_data['status'] = 'unhealthy'
            health_data['error'] = str(e)
            
            end_time = asyncio.get_event_loop().time()
            health_data['response_time_ms'] = round((end_time - start_time) * 1000, 2)
            
            await log_error(
                e,
                severity=ErrorSeverity.CRITICAL,
                category=ErrorCategory.DATABASE,
                additional_context={'operation': 'health_check'}
            )
        
        return health_data


# Global instances
transaction_manager = TransactionManager()
bulk_operation_manager = BulkOperationManager()
db_health_checker = DatabaseHealthChecker()


def transactional(retry: bool = True, savepoint: bool = False):
    """
    Decorator for automatic transaction management
    
    Args:
        retry: Whether to retry on retryable errors
        savepoint: Use savepoint instead of full transaction
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if session is already provided
            session = kwargs.get('db') or kwargs.get('session')
            
            if session:
                # Use existing session with savepoint
                async with transaction_manager.transaction(session, savepoint=savepoint):
                    return await func(*args, **kwargs)
            else:
                # Create new session
                async with transaction_manager.transaction() as session:
                    # Inject session into function
                    if 'db' not in kwargs and 'session' not in kwargs:
                        kwargs['db'] = session
                    return await func(*args, **kwargs)
        
        return wrapper
    return decorator


async def execute_with_retry(operation: Callable, *args, **kwargs) -> Any:
    """Convenience function for retrying database operations"""
    return await transaction_manager.execute_with_retry(operation, *args, **kwargs)


async def get_database_health() -> Dict[str, Any]:
    """Get database health status"""
    return await db_health_checker.check_database_health()