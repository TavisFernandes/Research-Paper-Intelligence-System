"""Environment-backed application configuration."""
from dataclasses import dataclass
import os


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_index: str = os.getenv("REDIS_INDEX", "paper_chunks")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "Qwen/Qwen3.5-9B")
    led_model: str = os.getenv("LED_MODEL", "allenai/led-base-16384")
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1200"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "150"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
    allow_origins: str = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173")
    use_local_fallbacks: bool = _bool("USE_LOCAL_FALLBACKS", True)


settings = Settings()
