"""
User Data Database Connection

使用统一数据库，操作 user_data schema
"""
from contextlib import contextmanager
import traceback

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from loguru import logger

from ...config import settings
from .models import Base, SCHEMA_NAME


# 使用统一数据库连接
engine = create_engine(
    url=settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)

Session = sessionmaker(bind=engine, expire_on_commit=False)


def init_user_data_schema():
    """
    Initialize user_data schema and create tables if not exist.
    Call this at app startup.
    """
    try:
        with engine.connect() as conn:
            # Create schema if not exists
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
            conn.commit()
            logger.info(f"Schema '{SCHEMA_NAME}' ensured")

        # Create tables
        Base.metadata.create_all(bind=engine)
        logger.info("User data tables created/verified")
    except Exception as e:
        logger.error(f"Failed to initialize user_data schema: {e}")
        raise


@contextmanager
def session_generator():
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"User data session error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        session.rollback()
        raise
    finally:
        session.close()
