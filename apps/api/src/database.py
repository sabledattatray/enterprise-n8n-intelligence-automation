import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from apps.api.src.config import settings

# In Windows local testing, use LOCAL_DATABASE_URL if host is localhost/127.0.0.1
db_url = settings.DATABASE_URL
if os.environ.get("RUNNING_IN_DOCKER") != "true" and "postgres:5432" in db_url:
    db_url = settings.LOCAL_DATABASE_URL

engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency for database session injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health() -> bool:
    """Verifies that the database is reachable and accepting queries."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception:
        return False

