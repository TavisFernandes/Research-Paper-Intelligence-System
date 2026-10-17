"""Embedding + vector-store indexing of processed papers, and start-up re-synchronisation."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from embeddings import get_embedder
from retrieval import invalidate_lexical_index
from vector_store import get_vector_store

logger = logging.getLogger(__name__)


def index_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
    """Embed a paper's chunks and (re)write them into the vector store. Idempotent per paper."""
    chunks: List[Dict[str, Any]] = list(paper.get("chunks", []))
    embedder, store = get_embedder(), get_vector_store()
    info = {"chunk_count": len(chunks), "indexed": False, "embedding_backend": None, "vector_store": store.backend}
    if not chunks:
        return info
    vectors = embedder.encode([str(c["text"]) for c in chunks])
    store.ensure_index(embedder.dimension)
    store.delete_paper(str(paper["paper_id"]))
    store.upsert_chunks(chunks, vectors)  # type: ignore[arg-type]
    invalidate_lexical_index()
    info.update({"indexed": True, "embedding_backend": embedder.backend, "embedding_model": embedder.model_name,
                 "dimension": embedder.dimension, "semantic": embedder.is_semantic, "vector_store": store.backend,
                 "persistent": bool(store.persistent)})
    return info


def sync_index() -> Dict[str, int]:
    """Re-index stored papers that are missing from the vector store (after a restart or a Redis flush)."""
    from pdf_processing.storage import list_papers, save_paper

    store = get_vector_store()
    restored = failed = 0
    for paper in list_papers():
        pid = str(paper["paper_id"])
        if not paper.get("chunks") or store.count(pid) >= len(paper["chunks"]):  # type: ignore[arg-type]
            continue
        try:
            paper["indexing"] = index_paper(paper)
            save_paper(paper)
            restored += 1
        except Exception:
            logger.exception("Could not re-index %s", pid)
            failed += 1
    invalidate_lexical_index()
    return {"restored": restored, "failed": failed}
