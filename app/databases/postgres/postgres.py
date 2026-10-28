from contextlib import contextmanager
import traceback

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from loguru import logger

from ...config import settings

engine = create_engine(
    url=settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=-1,
    pool_recycle=3600,
)

Session = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_generator():
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Database session error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        session.rollback()
        raise
    finally:
        session.close()
