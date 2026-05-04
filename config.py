import os
from dotenv import load_dotenv

# Load environment variables from a .env file into the system environment.
load_dotenv()

class Settings:
    """
    Application configuration settings.
    Retrieves values from environment variables with sensible defaults for the Dockerized environment.
    """
    # PostgreSQL Operational DB Settings
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "admin")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "adminpassword")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "ops_db")
    # In a Docker network, the host must be the container name, not localhost.
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "dwh_postgres")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    
    # Dynamically construct the SQLAlchemy Database URL
    SQLALCHEMY_DATABASE_URL: str = (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )

    # ClickHouse DWH Settings
    CLICKHOUSE_USER: str = os.getenv("CLICKHOUSE_USER", "admin")
    CLICKHOUSE_PASSWORD: str = os.getenv("CLICKHOUSE_PASSWORD", "adminpassword")
    CLICKHOUSE_DB: str = os.getenv("CLICKHOUSE_DB", "analytics_db")
    CLICKHOUSE_HOST: str = os.getenv("CLICKHOUSE_HOST", "dwh_clickhouse")
    CLICKHOUSE_PORT: str = os.getenv("CLICKHOUSE_PORT", "9000")

    # JWT Security Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# Instantiate the settings object to be imported across the application.
settings = Settings()