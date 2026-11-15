"""AutoAnalyst system-wide configuration and loop limits."""

import os
from pydantic import BaseModel


class Settings(BaseModel):
    """Configurable system runtime parameters, limits, and timeouts."""

    # Project paths
    BASE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    UPLOAD_DIR: str = os.path.join(DATA_DIR, "uploads")
    CHECKPOINTS_DB_PATH: str = os.path.join(DATA_DIR, "checkpoints.sqlite")
    EVENTS_DB_PATH: str = os.path.join(DATA_DIR, "events.sqlite")

    # LLM configuration (read strictly from env vars, never hardcoded)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "mock-analyst-v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_CALL_BUDGET: int = int(os.getenv("LLM_CALL_BUDGET", "30"))
    LLM_TOKEN_BUDGET: int = int(os.getenv("LLM_TOKEN_BUDGET", "100000"))

    # Docker sandbox constraints
    SANDBOX_PROVIDER: str = os.getenv("SANDBOX_PROVIDER", "auto")
    SANDBOX_IMAGE: str = os.getenv("SANDBOX_IMAGE", "autoanalyst-sandbox:latest")
    SANDBOX_TIMEOUT_SECONDS: int = int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "30"))
    SANDBOX_MEM_LIMIT: str = "512m"
    SANDBOX_PIDS_LIMIT: int = 50
    SANDBOX_CPU_QUOTA: int = 100000
    MAX_SCRIPT_BYTES: int = 64 * 1024  # 64 KB
    MAX_LOG_BYTES: int = 10 * 1024  # 10 KB

    # Loop guards and resilience caps
    MAX_RETRIES_PER_STEP: int = 3
    MAX_TOTAL_ITERATIONS: int = 25
    MAX_PLAN_STEPS: int = 6
    MAX_PAUSE_TTL_SECONDS: int = 1800  # 30 minutes
    ACTIVE_WALL_CLOCK_LIMIT_SECONDS: int = 300  # 5 minutes active time

    # Upload constraints
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    ALLOWED_EXTENSIONS: set = {".csv", ".parquet"}


settings = Settings()

# Ensure required runtime directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
