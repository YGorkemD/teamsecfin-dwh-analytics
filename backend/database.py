"""
Enterprise Database Connection Management Module.
Handles configurations and robust session generation for both the operational 
PostgreSQL database (OLTP) and the ClickHouse Data Warehouse (OLAP) using SQLAlchemy ORM.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

# =====================================================================
# POSTGRESQL OPERATIONAL DATABASE CONFIGURATION (OLTP)
# =====================================================================

# Construct the PostgreSQL connection URI dynamically from environment variables
SQLALCHEMY_DATABASE_URL = (
    f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

# Initialize the engine for the operational database
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Configure session factory: autocommit is disabled to allow explicit transaction management
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    FastAPI dependency that yields a PostgreSQL database session.
    Ensures that the connection is safely and automatically closed after the request lifecycle.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =====================================================================
# CLICKHOUSE ANALYTICS DATABASE CONFIGURATION (OLAP / DWH)
# =====================================================================

# Utilizing clickhouse+native dialect for optimal analytical query performance
CLICKHOUSE_URL = (
    f"clickhouse+native://{settings.CLICKHOUSE_USER}:{settings.CLICKHOUSE_PASSWORD}"
    f"@{settings.CLICKHOUSE_HOST}:{settings.CLICKHOUSE_PORT}/{settings.CLICKHOUSE_DB}"
)

# Initialize the engine specifically for the Data Warehouse
ch_engine = create_engine(CLICKHOUSE_URL)
ClickHouseSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ch_engine)

def get_clickhouse_session():
    """
    FastAPI dependency that yields a ClickHouse SQLAlchemy ORM session.
    Guarantees resource release post-query execution to prevent connection leaks.
    """
    session = ClickHouseSessionLocal()
    try:
        yield session
    finally:
        session.close()