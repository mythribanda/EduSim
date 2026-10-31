
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger("EduSim.config.settings")

env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")


def validate_supabase_url(url: str | None = None) -> str | None:
    target_url = url if url is not None else os.getenv("SUPABASE_URL")
    if not target_url:
        return None
    if "your-project" in target_url:
        raise RuntimeError("Invalid SUPABASE_URL placeholder.")
    return target_url


def validate_jwt_secret(secret: str | None = None) -> str:
    target_secret = secret if secret is not None else (
        os.getenv("JWT_SECRET") or os.getenv("JWT_SECRET_KEY")
    )
    if not target_secret:
        raise RuntimeError("JWT_SECRET environment variable is missing.")
    if len(target_secret.strip()) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 characters long.")
    return target_secret.strip()


def validate_config():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is missing.")
    validate_jwt_secret()


class Settings:
    @property
    def SUPABASE_URL(self) -> str | None:
        return validate_supabase_url()


settings = Settings()
