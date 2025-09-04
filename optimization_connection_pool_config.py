# Database Connection Pool Optimization
# Add this configuration to your database setup

# For SQLAlchemy async engine
OPTIMIZED_DB_CONFIG = {
    'poolclass': QueuePool,
    'pool_size': 25,              # Base connections (increased from default 5)
    'max_overflow': 35,           # Additional connections when needed
    'pool_timeout': 30,           # Timeout for getting connection
    'pool_recycle': 3600,         # Recycle connections every hour
    'pool_pre_ping': True,        # Validate connections before use
    
    # Connection args for PostgreSQL
    'connect_args': {
        'server_settings': {
            'jit': 'off',           # Disable JIT for consistent performance
            'application_name': 'mita_finance_app'
        },
        'command_timeout': 60,
        'prepared_statement_cache_size': 100
    }
}

# For async database URL
def get_optimized_async_engine(database_url: str):
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import QueuePool
    
    # Ensure asyncpg driver
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    return create_async_engine(database_url, **OPTIMIZED_DB_CONFIG)
