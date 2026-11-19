"""Application configuration loaded exclusively from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BASE_DIR.parent
DEFAULT_ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(DEFAULT_ENV_FILE) if DEFAULT_ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'healthyarn.db').as_posix()}"
    STT_PROVIDER: str = "mock"  # yarngpt | spitch | mock | hf
    SPITCH_API_KEY: str = ""
    YARNGPT_API_KEY: str = ""
    YARNGPT_BASE_URL: str = "https://api.yarngpt.ai"
    TTS_PROVIDER_ORDER: str = "spitch,yarngpt"
    TTS_YO_PROVIDER_ORDER: str = "spitch,yarngpt"
    SPITCH_VOICE_YO: str = "sade"
    YARNGPT_VOICE_YO: str = "wura"
    TTS_ENABLE_SPITCH_TONE_MARK: bool = True
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    EMBEDDING_MODEL: str = "sentence-transformers/LaBSE"
    MATCH_THRESHOLD: float = 0.62
    MATCH_MARGIN: float = 0.03
    JWT_SECRET: str = "dev-only-override-via-env"
    JWT_EXPIRES_HOURS: int = 8
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    MAX_AUDIO_SECONDS: int = 15
    MAX_AUDIO_BYTES: int = 1_048_576  # 1 MB
    STT_TIMEOUT_SECONDS: float = 15.0
    LOG_UNMATCHED_TEXT: bool = False
    DEMO_MODE: bool = False
    CONTENT_REVIEWED: bool = True
    COOKIE_SECURE: bool = False  # Set true behind HTTPS in production
    DISABLE_HEAVY_EMBEDDINGS: bool = False

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def content_dir(self) -> Path:
        return REPO_ROOT / "content"

    @property
    def static_audio_dir(self) -> Path:
        return BASE_DIR / "static" / "audio"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
