<<<<<<< HEAD
"""Vector store factory. The backend is chosen by ``VECTOR_STORE_BACKEND`` (auto | redis | memory)."""
from __future__ import annotations

import logging
import threading
from typing import Optional

from config import settings
from errors import VectorStoreUnavailable

from .base import VectorStore
from .memory_store import MemoryVectorStore
from .redis_store import RedisVectorStore

logger = logging.getLogger(__name__)
_store: Optional[VectorStore] = None
_lock = threading.Lock()


def create_vector_store() -> VectorStore:
    mode = settings.vector_store_backend
    if mode == "memory":
        return MemoryVectorStore()
    try:
        store = RedisVectorStore()
        store.verify()
        return store
    except VectorStoreUnavailable as exc:
        if mode == "redis":
            raise
        logger.warning("Redis unavailable (%s) - using the NON-PERSISTENT in-memory store.", exc.public_message)
        return MemoryVectorStore(degraded_reason=exc.public_message)


def get_vector_store() -> VectorStore:
    global _store
    with _lock:
        if _store is None:
            _store = create_vector_store()
        return _store


def set_vector_store(store: Optional[VectorStore]) -> None:
    global _store
    with _lock:
        _store = store


__all__ = ["MemoryVectorStore", "RedisVectorStore", "VectorStore", "get_vector_store", "set_vector_store", "create_vector_store"]
=======
from .redis_store import RedisVectorStore, vector_store

__all__ = ["RedisVectorStore", "vector_store"]
>>>>>>> origin/main
