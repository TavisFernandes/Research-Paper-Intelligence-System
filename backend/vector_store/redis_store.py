"""Redis Stack (RediSearch) vector store using HNSW/FLAT KNN with metadata filters.

Requires a Redis server with the RediSearch module (e.g. ``redis/redis-stack-server``).
Plain Redis without that module is detected and reported with a clear error.
Persistence is a property of the *server* configuration (see docker-compose.yml, AOF enabled).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from config import settings
from errors import VectorStoreUnavailable

logger = logging.getLogger(__name__)

_TEXT_FIELDS = ("chunk_id", "paper_id", "section_name", "heading", "text", "title", "filename")
_NUM_FIELDS = ("page_start", "page_end", "chunk_index")
_RETURN_FIELDS = ("vector_score", *_TEXT_FIELDS, "page_start", "page_end", "chunk_index", "meta")


def escape_tag(value: str) -> str:
    """Escape RediSearch TAG punctuation (e.g. hyphens in paper ids)."""
    return re.sub(r"([^\w])", r"\\\1", str(value))


def _decode(value: Any) -> Any:
    return value.decode("utf-8", errors="replace") if isinstance(value, (bytes, bytearray)) else value


class RedisVectorStore:
    backend = "redis"
    persistent = True  # server-side; true only if the server runs with AOF/RDB (see docker-compose.yml)

    def __init__(self, url: Optional[str] = None, index_name: Optional[str] = None, client: Any = None):
        self.url = url or settings.redis_url
        self.index_name = index_name or settings.redis_index
        self.prefix = f"{self.index_name}:doc:"
        self.meta_key = f"{self.index_name}:meta"
        self._dimension: Optional[int] = None
        if client is not None:
            self.client = client
        else:
            try:
                import redis
            except ImportError as exc:
                raise VectorStoreUnavailable("The 'redis' Python package is not installed.") from exc
            self.client = redis.from_url(self.url, decode_responses=False, socket_connect_timeout=3, socket_timeout=10)

    # ---------------------------------------------------------------- connectivity
    def _dimension_mismatch_error(self, index_dim: int, query_dim: int, model: Optional[str] = None) -> VectorStoreUnavailable:
        model_note = f" ({model})" if model else ""
        return VectorStoreUnavailable(
            f"Redis index '{self.index_name}' was built with {index_dim}-d vectors{model_note} "
            f"but the current embedder produces {query_dim}-d. "
            'Rebuild with POST /api/reindex {"reset": true} after the embedding model is stable.'
        )

    def _cmd(self, *args: Any) -> Any:
        try:
            return self.client.execute_command(*args)
        except Exception as exc:
            text = str(exc).lower()
            if "unknown command" in text and "ft." in text:
                raise VectorStoreUnavailable(
                    "Redis is reachable but the RediSearch module is missing. Use Redis Stack "
                    "(docker compose up -d redis) or set VECTOR_STORE_BACKEND=memory for local testing."
                ) from exc
            if "unknown index name" in text or "no such index" in text:
                raise
            # Query vector byte length must match FLOAT32 * DIM (e.g. after switching to hashing fallback).
            if "query vector blob size" in text or "does not match index's expected size" in text:
                query_dim = self._dimension
                stored = self.client.get(self.meta_key)
                index_dim = None
                model = None
                if stored:
                    meta = json.loads(_decode(stored))
                    index_dim = int(meta["dimension"]) if meta.get("dimension") is not None else None
                    model = meta.get("model")
                if index_dim is not None and query_dim is not None:
                    raise self._dimension_mismatch_error(index_dim, query_dim, model) from exc
                raise VectorStoreUnavailable(
                    f"Redis index '{self.index_name}' vector dimension does not match the current embedder. "
                    'Rebuild with POST /api/reindex {"reset": true}.'
                ) from exc
            raise VectorStoreUnavailable(f"Redis request failed ({type(exc).__name__}). Check REDIS_URL and that the server is running.") from exc

    def verify(self) -> None:
        """Validate connectivity and RediSearch availability (raises VectorStoreUnavailable)."""
        try:
            self.client.ping()
        except Exception as exc:
            raise VectorStoreUnavailable("Cannot connect to Redis. Start it with `docker compose up -d redis` and check REDIS_URL.") from exc
        self._cmd("FT._LIST")

    # ------------------------------------------------------------------- index
    def _index_exists(self) -> bool:
        return self.index_name.encode() in [_i if isinstance(_i, bytes) else str(_i).encode() for _i in self._cmd("FT._LIST")]

    def ensure_index(self, dimension: int) -> None:
        self.verify()
        stored = self.client.get(self.meta_key)
        if self._index_exists():
            if stored:
                meta = json.loads(_decode(stored))
                index_dim = int(meta.get("dimension", dimension))
                if index_dim != dimension:
                    raise self._dimension_mismatch_error(index_dim, dimension, meta.get("model"))
            self._dimension = dimension
            return
        algorithm = settings.redis_index_algorithm if settings.redis_index_algorithm in ("HNSW", "FLAT") else "HNSW"
        vector_args: List[Any] = ["TYPE", "FLOAT32", "DIM", dimension, "DISTANCE_METRIC", "COSINE"]
        if algorithm == "HNSW":
            vector_args += ["M", settings.redis_hnsw_m, "EF_CONSTRUCTION", settings.redis_hnsw_ef_construction]
        self._cmd(
            "FT.CREATE", self.index_name, "ON", "HASH", "PREFIX", 1, self.prefix, "SCHEMA",
            "chunk_id", "TAG", "paper_id", "TAG", "section_name", "TAG", "filename", "TAG",
            "text", "TEXT", "title", "TEXT", "page_start", "NUMERIC", "page_end", "NUMERIC",
            "embedding", "VECTOR", algorithm, len(vector_args), *vector_args,
        )
        from embeddings import get_embedder

        self.client.set(self.meta_key, json.dumps({"dimension": dimension, "model": get_embedder().model_name, "algorithm": algorithm}))
        self._dimension = dimension

    def reset_index(self) -> None:
        """Drop the index and every stored document (used when the embedding model changes)."""
        if self._index_exists():
            self._cmd("FT.DROPINDEX", self.index_name, "DD")
        self.client.delete(self.meta_key)
        self._dimension = None

    # -------------------------------------------------------------------- writes
    def upsert_chunks(self, chunks: Sequence[Dict[str, Any]], vectors: Sequence[Sequence[float]]) -> int:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        if not chunks:
            return 0
        self.ensure_index(len(vectors[0]))
        try:
            pipe = self.client.pipeline(transaction=False)
            for chunk, vector in zip(chunks, vectors):
                array = np.asarray(vector, dtype=np.float32)
                if array.shape[0] != self._dimension:
                    raise VectorStoreUnavailable("Vector dimension does not match the index dimension.")
                mapping: Dict[str, Any] = {name: str(chunk.get(name) or "") for name in _TEXT_FIELDS}
                mapping.update({name: int(chunk.get(name) or 0) for name in _NUM_FIELDS})
                extra = {k: v for k, v in chunk.items() if k not in mapping}
                mapping["meta"] = json.dumps(extra, default=str)
                mapping["embedding"] = array.tobytes()
                # HSET on the same key overwrites fields: re-ingesting a chunk never duplicates it.
                pipe.hset(f"{self.prefix}{chunk['chunk_id']}", mapping=mapping)
            pipe.execute()
        except VectorStoreUnavailable:
            raise
        except Exception as exc:
            raise VectorStoreUnavailable(f"Failed to write chunks to Redis ({type(exc).__name__}).") from exc
        return len(chunks)

    def _paper_keys(self, paper_id: str) -> List[bytes]:
        keys = []
        try:
            for key in self.client.scan_iter(match=f"{self.prefix}{paper_id}_*", count=500):
                if _decode(self.client.hget(key, "paper_id")) == paper_id:
                    keys.append(key)
        except Exception as exc:
            raise VectorStoreUnavailable(f"Redis scan failed ({type(exc).__name__}).") from exc
        return keys

    def delete_paper(self, paper_id: str) -> int:
        keys = self._paper_keys(paper_id)
        if keys:
            try:
                self.client.delete(*keys)
            except Exception as exc:
                raise VectorStoreUnavailable(f"Redis delete failed ({type(exc).__name__}).") from exc
        return len(keys)

    # --------------------------------------------------------------------- reads
    def build_query(self, limit: int, paper_ids: Optional[Sequence[str]], section_names: Optional[Sequence[str]]) -> str:
        filters = []
        if paper_ids:
            filters.append("@paper_id:{" + "|".join(escape_tag(p) for p in paper_ids) + "}")
        if section_names:
            filters.append("@section_name:{" + "|".join(escape_tag(s) for s in section_names) + "}")
        prefilter = "(" + " ".join(filters) + ")" if filters else "*"
        return f"{prefilter}=>[KNN {int(limit)} @embedding $vec AS vector_score]"

    def search(self, vector: Sequence[float], limit: int = 8, paper_ids: Optional[Sequence[str]] = None,
               section_names: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
        self.verify()
        array = np.asarray(vector, dtype=np.float32)
        query_dim = int(array.shape[0])
        self._dimension = query_dim
        # Fail fast with an actionable message when the live embedder no longer matches the index.
        stored = self.client.get(self.meta_key)
        if stored and self._index_exists():
            meta = json.loads(_decode(stored))
            index_dim = int(meta["dimension"]) if meta.get("dimension") is not None else None
            if index_dim is not None and index_dim != query_dim:
                raise self._dimension_mismatch_error(index_dim, query_dim, meta.get("model"))
        query = self.build_query(limit, paper_ids, section_names)
        try:
            reply = self._cmd("FT.SEARCH", self.index_name, query, "PARAMS", 2, "vec", array.tobytes(),
                              "SORTBY", "vector_score", "ASC", "RETURN", len(_RETURN_FIELDS), *_RETURN_FIELDS,
                              "LIMIT", 0, int(limit), "DIALECT", 2)
        except Exception as exc:
            if "unknown index name" in str(exc).lower() or "no such index" in str(exc).lower():
                return []  # nothing has been indexed yet
            raise
        return self.parse_reply(reply)

    @staticmethod
    def parse_reply(reply: Any) -> List[Dict[str, Any]]:
        def field_mapping(raw: Any) -> Dict[str, Any]:
            if isinstance(raw, dict):
                return {_decode(key): _decode(value) for key, value in raw.items()}
            if isinstance(raw, (list, tuple)) and len(raw) % 2 == 0:
                return {_decode(raw[i]): _decode(raw[i + 1]) for i in range(0, len(raw), 2)}
            raise VectorStoreUnavailable("Redis returned an invalid vector search result.")

        if isinstance(reply, dict):
            response = {_decode(key): value for key, value in reply.items()}
            documents = response.get("results")
            if not isinstance(documents, list):
                raise VectorStoreUnavailable("Redis returned an invalid vector search response.")
            rows = []
            for document in documents:
                if not isinstance(document, dict):
                    raise VectorStoreUnavailable("Redis returned an invalid vector search result.")
                document = {_decode(key): value for key, value in document.items()}
                fields = field_mapping(document.get("extra_attributes", {}))
                fields.update(field_mapping(document.get("values", [])))
                rows.append(fields)
        elif isinstance(reply, (list, tuple)):
            if len(reply) % 2 != 1:
                raise VectorStoreUnavailable("Redis returned an invalid vector search response.")
            rows = [field_mapping(reply[i + 1]) for i in range(1, len(reply), 2)]
        else:
            raise VectorStoreUnavailable("Redis returned an invalid vector search response.")

        results: List[Dict[str, Any]] = []
        for fields in rows:
            extra = json.loads(fields.pop("meta", "{}") or "{}")
            distance = float(fields.pop("vector_score", 1.0))
            record: Dict[str, Any] = {**extra, **fields}
            for name in ("page_start", "page_end", "chunk_index"):
                if name in record:
                    record[name] = int(float(record[name]))
            record["score"] = round(1.0 - distance, 5)  # cosine similarity
            results.append(record)
        return results

    def count(self, paper_id: Optional[str] = None) -> int:
        if paper_id:
            return len(self._paper_keys(paper_id))
        return sum(1 for _ in self.client.scan_iter(match=f"{self.prefix}*", count=1000))

    def all_chunks(self, paper_ids: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for key in self.client.scan_iter(match=f"{self.prefix}*", count=1000):
            raw = self.client.hgetall(key)
            fields = {_decode(k): _decode(v) for k, v in raw.items() if _decode(k) != "embedding"}
            if paper_ids and fields.get("paper_id") not in paper_ids:
                continue
            extra = json.loads(fields.pop("meta", "{}") or "{}")
            record = {**extra, **fields}
            for name in _NUM_FIELDS:
                if name in record:
                    record[name] = int(float(record[name]))
            out.append(record)
        return out

    def health(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {"backend": self.backend, "url_host": re.sub(r"//[^@]*@", "//***@", self.url), "index": self.index_name}
        try:
            self.verify()
            info["connected"] = True
            info["redisearch"] = True
            info["index_exists"] = self._index_exists()
            info["chunks"] = self.count()
            aof = self.client.config_get("appendonly")
            info["persistent"] = _decode(next(iter(aof.values()), b"no")) == "yes" if aof else False
        except VectorStoreUnavailable as exc:
            info.update({"connected": False, "error": exc.public_message})
        return info
