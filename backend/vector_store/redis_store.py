"""Redis vector repository with an in-process fallback for development and tests."""
from __future__ import annotations
import math
from typing import Any
from config import settings


def _cosine(left: list[float], right: list[float]) -> float:
    product = sum(a * b for a, b in zip(left, right))
    norms = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return product / norms if norms else 0.0


class RedisVectorStore:
    def __init__(self, url: str = settings.redis_url, index_name: str = settings.redis_index):
        self.index_name, self._records, self.client = index_name, {}, None
        self.backend = "memory"
        try:
            import redis
            self.client = redis.from_url(url, decode_responses=True)
            self.client.ping()
            self.backend = "redis"
        except Exception:
            self.client = None

    def upsert_chunks(self, chunks: list[dict[str, Any]], vectors: list[list[float]]) -> int:
        for chunk, vector in zip(chunks, vectors):
            record = {**chunk, "vector": vector}
            self._records[str(chunk["chunk_id"])] = record
            if self.client:
                import json
                self.client.hset(f"{self.index_name}:{chunk['chunk_id']}", mapping={"payload": json.dumps(record)})
        return len(chunks)

    def delete_paper(self, paper_id: str) -> int:
        keys = [key for key, value in self._records.items() if value["paper_id"] == paper_id]
        for key in keys:
            del self._records[key]
            if self.client:
                self.client.delete(f"{self.index_name}:{key}")
        return len(keys)

    def search(self, vector: list[float], limit: int = 8, paper_ids: list[str] | None = None,
               section_name: str | None = None) -> list[dict[str, Any]]:
        records = self._records.values()
        matches = []
        for item in records:
            if paper_ids and item["paper_id"] not in paper_ids:
                continue
            if section_name and item["section_name"] != section_name:
                continue
            matches.append({k: v for k, v in item.items() if k != "vector"} | {"score": round(_cosine(vector, item["vector"]), 5)})
        return sorted(matches, key=lambda match: match["score"], reverse=True)[:limit]


vector_store = RedisVectorStore()
