"""Environment-backed application configuration.

All values are read from environment variables (optionally loaded from a ``.env``
file by ``python-dotenv`` when it is installed). Secrets such as ``LLM_API_KEY``
are never given defaults and are never logged or returned by the API.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional
        return
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)
            break


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    """Runtime configuration. Mutable so tests can use ``dataclasses.replace``."""

    # --- Redis / vector store -------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    redis_index: str = "paper_chunks"
    # auto  -> use Redis Stack when reachable, otherwise an explicitly reported in-memory store
    # redis -> require Redis Stack (RediSearch); raise a clear error otherwise
    # memory-> in-process store only (tests / quick demos; NOT persisted)
    vector_store_backend: str = "auto"
    redis_hnsw_m: int = 16
    redis_hnsw_ef_construction: int = 200
    redis_index_algorithm: str = "HNSW"  # HNSW or FLAT

    # --- Embeddings -----------------------------------------------------------
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "auto"  # auto | cpu | cuda | mps
    embedding_batch_size: int = 16
    embedding_max_length: int = 512
    # Hashing embeddings are NOT semantic. They exist only so the app can start offline.
    allow_hashing_fallback: bool = True
    hashing_dimensions: int = 384

    # --- Retrieval ------------------------------------------------------------
    default_top_k: int = 8
    retrieval_mode: str = "hybrid"  # dense | lexical | hybrid
    min_dense_score: float = 0.35  # cosine floor for BGE-M3 style embeddings
    min_lexical_coverage: float = 0.5  # share of query terms a chunk must contain
    rrf_k: int = 60

    # --- LLM ------------------------------------------------------------------
    llm_base_url: str = ""
    llm_api_key: str = field(default="", repr=False)
    llm_model: str = "Qwen/Qwen3.5-9B"
    llm_timeout_seconds: float = 60.0
    llm_max_tokens: int = 700
    llm_temperature: float = 0.1

    # --- Summarisation --------------------------------------------------------
    led_model: str = "allenai/led-base-16384"
    enable_led: bool = False
    led_max_input_tokens: int = 16384
    led_window_tokens: int = 12000
    led_max_summary_tokens: int = 256
    led_min_summary_tokens: int = 40

    # --- Ingestion ------------------------------------------------------------
    chunk_size: int = 1200
    chunk_overlap: int = 150
    max_upload_bytes: int = 20 * 1024 * 1024
    ocr_enabled: bool = True
    ocr_languages: str = "en"
    ocr_dpi: int = 200
    ocr_min_words: int = 15
    index_references: bool = False
    storage_dir: str = ""

    # --- API ------------------------------------------------------------------
    allow_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()
        return cls(
            redis_url=os.getenv("REDIS_URL", cls.redis_url),
            redis_index=os.getenv("REDIS_INDEX", cls.redis_index),
            vector_store_backend=os.getenv("VECTOR_STORE_BACKEND", "auto").lower(),
            redis_hnsw_m=_int("REDIS_HNSW_M", 16),
            redis_hnsw_ef_construction=_int("REDIS_HNSW_EF_CONSTRUCTION", 200),
            redis_index_algorithm=os.getenv("REDIS_INDEX_ALGORITHM", "HNSW").upper(),
            embedding_model=os.getenv("EMBEDDING_MODEL", cls.embedding_model),
            embedding_device=os.getenv("EMBEDDING_DEVICE", "auto").lower(),
            embedding_batch_size=_int("EMBEDDING_BATCH_SIZE", 16),
            embedding_max_length=_int("EMBEDDING_MAX_LENGTH", 512),
            allow_hashing_fallback=_bool("ALLOW_HASHING_FALLBACK", True),
            hashing_dimensions=_int("HASHING_DIMENSIONS", 384),
            default_top_k=_int("DEFAULT_TOP_K", 8),
            retrieval_mode=os.getenv("RETRIEVAL_MODE", "hybrid").lower(),
            min_dense_score=_float("MIN_DENSE_SCORE", 0.35),
            min_lexical_coverage=_float("MIN_LEXICAL_COVERAGE", 0.5),
            rrf_k=_int("RRF_K", 60),
            llm_base_url=os.getenv("LLM_BASE_URL", "").strip(),
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_model=os.getenv("LLM_MODEL", cls.llm_model),
            llm_timeout_seconds=_float("LLM_TIMEOUT_SECONDS", 60.0),
            llm_max_tokens=_int("LLM_MAX_TOKENS", 700),
            llm_temperature=_float("LLM_TEMPERATURE", 0.1),
            led_model=os.getenv("LED_MODEL", cls.led_model),
            enable_led=_bool("ENABLE_LED", False),
            led_max_input_tokens=_int("LED_MAX_INPUT_TOKENS", 16384),
            led_window_tokens=_int("LED_WINDOW_TOKENS", 12000),
            led_max_summary_tokens=_int("LED_MAX_SUMMARY_TOKENS", 256),
            led_min_summary_tokens=_int("LED_MIN_SUMMARY_TOKENS", 40),
            chunk_size=_int("CHUNK_SIZE", 1200),
            chunk_overlap=_int("CHUNK_OVERLAP", 150),
            max_upload_bytes=_int("MAX_UPLOAD_BYTES", 20 * 1024 * 1024),
            ocr_enabled=_bool("OCR_ENABLED", True),
            ocr_languages=os.getenv("OCR_LANGUAGES", "en"),
            ocr_dpi=_int("OCR_DPI", 200),
            ocr_min_words=_int("OCR_MIN_WORDS", 15),
            index_references=_bool("INDEX_REFERENCES", False),
            storage_dir=os.getenv("PAPER_STORAGE_DIR", ""),
            allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key)


settings = Settings.from_env()
