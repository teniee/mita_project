import os
import sys
from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context
from dotenv import load_dotenv

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Загружаем переменные из .env, если он есть в корне проекта
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Alembic Config
config = context.config
fileConfig(config.config_file_name)

# Импорт моделей (Base.metadata)
from app.db.models import Base  # noqa
target_metadata = Base.metadata

# Получаем строку подключения из переменной окружения
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL is not set in environment")

# Передаём строку подключения в Alembic напрямую (без % интерполяции)
config.attributes["sqlalchemy.url"] = DATABASE_URL

def run_migrations_offline():
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
