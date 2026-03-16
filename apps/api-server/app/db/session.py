from collections.abc import Generator
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.engine import build_database_engine

engine = build_database_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout_seconds=settings.db_pool_timeout_seconds,
    pool_recycle_seconds=settings.db_pool_recycle_seconds,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

