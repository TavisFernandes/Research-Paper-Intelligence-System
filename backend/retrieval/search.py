"""Dense, lexical and hybrid (RRF) retrieval with evidence-support flags."""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional, Sequence

from config import settings
from embeddings import get_embedder
from errors import InvalidInputError, VectorStoreUnavailable
from vector_store import get_vector_store

from .lexical import BM25Index, lexical_tokens

logger = logging.getLogger(__name__)
MODES = ("dense", "lexical", "hybrid")

_bm25_lock = threading.Lock()
_bm25_cache: Dict[str, Any] = {"index": None, "count": -1}


def invalidate_lexical_index() -> None:
    with _bm25_lock:
        _bm25_cache.update({"index": None, "count": -1})


def _lexical_index() -> BM25Index:
    store = get_vector_store()
    count = store.count()
    with _bm25_lock:
        if _bm25_cache["index"] is None or _bm25_cache["count"] != count:
            _bm25_cache["index"] = BM25Index(store.all_chunks())
            _bm25_cache["count"] = count
        return _bm25_cache["index"]


def _public(chunk: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "paper_id": chunk.get("paper_id"), "title": chunk.get("title") or None, "filename": chunk.get("filename") or None,
        "chunk_id": chunk.get("chunk_id"), "section_name": chunk.get("section_name"), "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"), "text": chunk.get("text"),
    }


def search_chunks(query: str, top_k: Optional[int] = None, mode: Optional[str] = None, paper_ids: Optional[Sequence[str]] = None,
                  section_names: Optional[Sequence[str]] = None, include_low_confidence: bool = False) -> Dict[str, Any]:
    """Retrieve ranked chunks. Result entries carry provenance, scores and a ``supported`` flag.

    ``supported`` is True when the chunk is dense-similar enough (cosine >= MIN_DENSE_SCORE,
    only trusted for semantic embedders) or lexically covers enough query terms.
    Unsupported chunks are dropped unless ``include_low_confidence`` is set.
    """
    query = (query or "").strip()
    if not query:
        raise InvalidInputError("Query must not be empty.")
    mode = (mode or settings.retrieval_mode).lower()
    if mode not in MODES:
        raise InvalidInputError(f"mode must be one of {', '.join(MODES)}.")
    top_k = top_k or settings.default_top_k
    pool = max(top_k * 4, 30)
    embedder = get_embedder()
    store = get_vector_store()
    warnings: List[str] = []
    if mode != "lexical" and not embedder.is_semantic:
        warnings.append("Embeddings are a non-semantic hashing fallback; ranking relies on lexical overlap. Install BGE-M3 for semantic retrieval.")

    dense_hits: List[Dict[str, Any]] = []
    if mode in ("dense", "hybrid"):
        try:
            dense_hits = store.search(embedder.encode(query), limit=pool, paper_ids=paper_ids, section_names=section_names)  # type: ignore[arg-type]
        except VectorStoreUnavailable as exc:
            # Hybrid can still answer from BM25 when the Redis vector dim no longer matches the embedder
            # (e.g. BGE-M3 index + hashing fallback without torch). Dense-only keeps the clear 503.
            message = exc.public_message
            if mode == "hybrid" and ("-d vectors" in message or "vector dimension does not match" in message):
                warnings.append(f"{message} Dense retrieval skipped; using lexical ranking.")
                logger.warning("Dense retrieval unavailable (%s); continuing with lexical ranking.", message)
                dense_hits = []
            else:
                raise
    # The BM25 index is always available: it also supplies the lexical-coverage evidence check.
    lexical_index = _lexical_index()
    lexical_hits: List[Dict[str, Any]] = []
    if mode in ("lexical", "hybrid"):
        lexical_hits = lexical_index.search(query, limit=pool, paper_ids=paper_ids, section_names=section_names)

    merged: Dict[str, Dict[str, Any]] = {}
    for rank, hit in enumerate(dense_hits, start=1):
        entry = merged.setdefault(str(hit["chunk_id"]), {**hit})
        entry["dense_score"] = hit["score"]
        entry["rrf"] = entry.get("rrf", 0.0) + 1.0 / (settings.rrf_k + rank)
    for rank, hit in enumerate(lexical_hits, start=1):
        entry = merged.setdefault(str(hit["chunk_id"]), {**hit})
        entry["bm25"] = hit["bm25"]
        entry["rrf"] = entry.get("rrf", 0.0) + 1.0 / (settings.rrf_k + rank)

    semantic = embedder.is_semantic
    results: List[Dict[str, Any]] = []
    for entry in merged.values():
        coverage = lexical_index.coverage(query, str(entry.get("text", "")))
        dense = entry.get("dense_score")
        dense_ok = semantic and dense is not None and dense >= settings.min_dense_score
        lexical_ok = coverage >= settings.min_lexical_coverage and len(set(lexical_tokens(query))) > 0
        row = _public(entry)
        row.update({
            "dense_score": dense, "bm25_score": entry.get("bm25"), "lexical_coverage": round(coverage, 3),
            "supported": bool(dense_ok or lexical_ok),
        })
        if mode == "dense":
            row["score"] = dense
            sort_key = dense or 0.0
        elif mode == "lexical":
            row["score"] = entry.get("bm25")
            sort_key = entry.get("bm25") or 0.0
        else:
            row["score"] = round(entry["rrf"], 5)
            sort_key = entry["rrf"]
        row["_sort"] = sort_key
        results.append(row)
    results.sort(key=lambda r: r["_sort"], reverse=True)
    for r in results:
        r.pop("_sort")
    supported = [r for r in results if r["supported"]]
    selected = results if include_low_confidence else supported
    selected = selected[:top_k]
    for rank, row in enumerate(selected, start=1):
        row["rank"] = rank
    return {"query": query, "mode": mode, "top_k": top_k, "results": selected, "returned": len(selected),
            "candidates": len(results), "filtered_low_confidence": len(results) - len(supported) if not include_low_confidence else 0,
            "embedding_backend": embedder.backend, "vector_store": store.backend, "warnings": warnings}
