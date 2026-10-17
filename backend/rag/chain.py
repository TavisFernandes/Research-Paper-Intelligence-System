<<<<<<< HEAD
"""Retrieval-augmented question answering with grounded, cited answers.

Flow (mirrors the ATML pipeline): query -> embedding -> Redis/hybrid retrieval -> evidence
selection -> prompt assembly -> LLM -> answer + evidence with paper/section/page metadata.
The orchestration is a thin explicit chain (no LangChain dependency required); each stage is a
separate function so a LangChain Runnable can wrap them if desired.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from config import settings
from errors import LLMUnavailable
from llm import llm
from retrieval import search_chunks

SYSTEM_PROMPT = (
    "You are a careful research assistant. Answer ONLY from the numbered evidence passages provided. "
    "Cite passages inline like [1] or [2][3]. If the passages do not contain the answer, reply exactly: "
    "\"The retrieved evidence is insufficient to answer this question.\" and say what is missing. "
    "Never add facts, numbers, datasets or conclusions that are not in the passages. "
    "If passages disagree, say so. Be concise."
)
INSUFFICIENT = "The retrieved evidence is insufficient to answer this question."
_CITE_RE = re.compile(r"\[(\d+)\]")


def select_evidence(hits: Sequence[Dict[str, Any]], max_chars: int = 9000, max_items: int = 8) -> List[Dict[str, Any]]:
    """Keep supported hits in rank order within a context budget."""
    selected, used = [], 0
    for hit in hits:
        if not hit.get("supported", True):
            continue
        length = len(str(hit.get("text", "")))
        if selected and used + length > max_chars:
            continue
        selected.append(hit)
        used += length
        if len(selected) >= max_items:
            break
    return selected


def build_messages(query: str, evidence: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    blocks = []
    for index, hit in enumerate(evidence, start=1):
        label = hit.get("title") or hit.get("filename") or hit.get("paper_id")
        pages = hit.get("page_start") if hit.get("page_start") == hit.get("page_end") else f"{hit.get('page_start')}-{hit.get('page_end')}"
        blocks.append(f"[{index}] (paper: {label}; id: {hit.get('paper_id')}; section: {hit.get('section_name')}; page: {pages})\n{hit.get('text')}")
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Evidence passages:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {query}\n\nAnswer with citations:"}]


def _evidence_payload(evidence: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    keys = ("paper_id", "title", "filename", "chunk_id", "section_name", "page_start", "page_end", "text", "score", "dense_score", "lexical_coverage")
    return [{"ref": i, **{k: hit.get(k) for k in keys}} for i, hit in enumerate(evidence, start=1)]


def answer_question(query: str, paper_ids: Optional[Sequence[str]] = None, section_names: Optional[Sequence[str]] = None,
                    top_k: Optional[int] = None, mode: Optional[str] = None) -> Dict[str, Any]:
    """Answer ``query`` from the indexed papers.

    ``status`` is one of: ``answered`` | ``insufficient_evidence`` | ``llm_unavailable`` | ``evidence_only``.
    Evidence is always returned so the user can verify or read the sources even if generation fails.
    """
    retrieval = search_chunks(query, top_k=top_k or settings.default_top_k, mode=mode, paper_ids=paper_ids, section_names=section_names)
    evidence = select_evidence(retrieval["results"])
    base: Dict[str, Any] = {"query": query, "evidence": _evidence_payload(evidence), "retrieved_count": retrieval["returned"],
                            "retrieval": {"mode": retrieval["mode"], "embedding_backend": retrieval["embedding_backend"],
                                          "vector_store": retrieval["vector_store"], "warnings": retrieval["warnings"]},
                            "generation": {"backend": llm.backend, "model": settings.llm_model if llm.configured else None}}
    if not evidence:
        return {**base, "status": "insufficient_evidence", "answer": INSUFFICIENT + " No sufficiently relevant passages were found in the selected papers.",
                "grounded": False, "citations_used": []}
    if not llm.configured:
        return {**base, "status": "evidence_only", "answer": None, "grounded": False, "citations_used": [],
                "message": "No language model is configured (set LLM_BASE_URL, LLM_API_KEY, LLM_MODEL). Showing the retrieved evidence only."}
    try:
        text = llm.chat(build_messages(query, evidence))
    except LLMUnavailable as exc:
        return {**base, "status": "llm_unavailable", "answer": None, "grounded": False, "citations_used": [], "message": exc.public_message}
    cited = sorted({int(n) for n in _CITE_RE.findall(text) if 1 <= int(n) <= len(evidence)})
    invalid = {int(n) for n in _CITE_RE.findall(text)} - set(range(1, len(evidence) + 1))
    refused = INSUFFICIENT.lower() in text.lower()
    out = {**base, "status": "insufficient_evidence" if refused else "answered", "answer": text,
           "grounded": bool(cited) and not refused, "citations_used": cited}
    if invalid:
        out["warnings"] = [f"The model cited non-existent passages: {sorted(invalid)}."]
    if not refused and not cited:
        out.setdefault("warnings", []).append("The answer contains no citations; treat it as unverified.")
    return out
=======
"""Grounded retrieval-augmented answering with citations."""
from embeddings import embedder
from llm import llm
from vector_store import vector_store


def answer_question(query: str, paper_ids: list[str] | None = None, section_name: str | None = None,
                    limit: int = 6) -> dict[str, object]:
    hits = vector_store.search(embedder.encode(query), limit=limit, paper_ids=paper_ids, section_name=section_name)
    citations = [{key: hit[key] for key in ("paper_id", "chunk_id", "section_name", "page_start", "page_end", "text", "score")}
                 for hit in hits]
    context = "\n\n".join(f"[{index + 1}] {hit['text']}" for index, hit in enumerate(hits))
    generated = llm.generate(query, context)
    if not generated:
        if not hits:
            generated = "I could not find supporting text in the selected papers."
        else:
            generated = "Based on the retrieved passages: " + " ".join(hit["text"] for hit in hits[:2])
    return {"answer": generated, "citations": citations, "retrieved_count": len(hits), "backend": llm.backend}
>>>>>>> origin/main
