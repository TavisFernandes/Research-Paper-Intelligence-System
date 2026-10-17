"""In-process vector store. Not persisted; used for tests and when Redis is unavailable in ``auto`` mode."""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from errors import VectorStoreUnavailable


class MemoryVectorStore:
    backend = "memory"
    persistent = False

    def __init__(self, degraded_reason: Optional[str] = None):
        self._records: Dict[str, Dict[str, Any]] = {}
        self._vectors: Dict[str, np.ndarray] = {}
        self._dimension: Optional[int] = None
        self._lock = threading.Lock()
        self.degraded_reason = degraded_reason

    def ensure_index(self, dimension: int) -> None:
        if self._dimension is not None and self._dimension != dimension and self._records:
            raise VectorStoreUnavailable(f"Index holds {self._dimension}-d vectors but the embedder produces {dimension}-d vectors; re-index all papers.")
        self._dimension = dimension

    def upsert_chunks(self, chunks: Sequence[Dict[str, Any]], vectors: Sequence[Sequence[float]]) -> int:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        with self._lock:
            for chunk, vector in zip(chunks, vectors):
                array = np.asarray(vector, dtype=np.float32)
                if self._dimension is None:
                    self._dimension = int(array.shape[0])
                if array.shape[0] != self._dimension:
                    raise VectorStoreUnavailable("Vector dimension does not match the index dimension.")
                key = str(chunk["chunk_id"])
                self._records[key] = dict(chunk)  # same chunk_id replaces the old record (no duplicates)
                self._vectors[key] = array
        return len(chunks)

    def delete_paper(self, paper_id: str) -> int:
        with self._lock:
            keys = [k for k, v in self._records.items() if v["paper_id"] == paper_id]
            for key in keys:
                del self._records[key], self._vectors[key]
        return len(keys)

    def search(self, vector: Sequence[float], limit: int = 8, paper_ids: Optional[Sequence[str]] = None,
               section_names: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
        query = np.asarray(vector, dtype=np.float32)
        norm = float(np.linalg.norm(query)) or 1.0
        keys = [k for k, r in self._records.items()
                if (not paper_ids or r["paper_id"] in paper_ids) and (not section_names or r["section_name"] in section_names)]
        if not keys:
            return []
        if self._dimension is not None and query.shape[0] != self._dimension:
            raise VectorStoreUnavailable("Query vector dimension does not match the index dimension.")
        matrix = np.vstack([self._vectors[k] for k in keys])
        norms = np.linalg.norm(matrix, axis=1)
        norms[norms == 0] = 1.0
        scores = matrix @ query / (norms * norm)
        order = np.argsort(-scores)[:limit]
        return [{**self._records[keys[i]], "score": round(float(scores[i]), 5)} for i in order]

    def count(self, paper_id: Optional[str] = None) -> int:
        if paper_id is None:
            return len(self._records)
        return sum(1 for r in self._records.values() if r["paper_id"] == paper_id)

    def all_chunks(self, paper_ids: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
        return [dict(r) for r in self._records.values() if not paper_ids or r["paper_id"] in paper_ids]

    def health(self) -> Dict[str, Any]:
        return {"backend": self.backend, "persistent": False, "connected": True, "chunks": len(self._records),
                "dimension": self._dimension, "degraded_reason": self.degraded_reason,
                "note": "In-memory store: data is lost on restart and rebuilt from stored papers at startup."}
