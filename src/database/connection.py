"""Database connection management.

This module provides the SQLAlchemy engine, session maker, and the
declarative base used by all models. It depends only on the config module.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency for providing a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
