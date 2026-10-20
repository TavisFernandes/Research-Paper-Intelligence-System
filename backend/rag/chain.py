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
from llm import get_chat_llm, llm
from retrieval import search_chunks

SYSTEM_PROMPT = (
    "You are a careful research assistant. Answer ONLY from the numbered evidence passages provided. "
    "Cite passages inline like [1] or [2][3]. If the passages do not contain the answer, reply exactly: "
    "\"The retrieved evidence is insufficient to answer this question.\" and say what is missing. "
    "Never add facts, numbers, datasets or conclusions that are not in the passages. "
    "If passages disagree, say so. Reply in at most 3 short sentences with citations."
)
INSUFFICIENT = "The retrieved evidence is insufficient to answer this question."
_CITE_RE = re.compile(r"\[(\d+)\]")
# Keep prompts small so local Ollama can answer within interactive latency budgets.
_QA_MAX_CHARS = 1400
_QA_MAX_ITEMS = 3
_QA_PASSAGE_CHARS = 280


def select_evidence(hits: Sequence[Dict[str, Any]], max_chars: int = _QA_MAX_CHARS, max_items: int = _QA_MAX_ITEMS) -> List[Dict[str, Any]]:
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


def _clip_passage(text: Any, limit: int = _QA_PASSAGE_CHARS) -> str:
    value = str(text or "")
    if len(value) <= limit:
        return value
    return value[:limit].rsplit(" ", 1)[0] + "…"


def build_messages(query: str, evidence: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    blocks = []
    for index, hit in enumerate(evidence, start=1):
        label = hit.get("title") or hit.get("filename") or hit.get("paper_id")
        pages = hit.get("page_start") if hit.get("page_start") == hit.get("page_end") else f"{hit.get('page_start')}-{hit.get('page_end')}"
        blocks.append(
            f"[{index}] (paper: {label}; id: {hit.get('paper_id')}; section: {hit.get('section_name')}; page: {pages})\n"
            f"{_clip_passage(hit.get('text'))}"
        )
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Evidence passages:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {query}\n\nAnswer with citations:"}]


def _evidence_payload(evidence: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    keys = ("paper_id", "title", "filename", "chunk_id", "section_name", "page_start", "page_end", "text", "score", "dense_score", "lexical_coverage")
    return [{"ref": i, **{k: hit.get(k) for k in keys}} for i, hit in enumerate(evidence, start=1)]


def _extractive_cited_answer(evidence: Sequence[Dict[str, Any]], limit: int = 3) -> str:
    """Fast grounded answer from evidence when the generative model cannot meet the latency budget."""
    parts: List[str] = []
    for index, hit in enumerate(evidence[:limit], start=1):
        text = re.sub(r"\s+", " ", str(hit.get("text") or "")).strip()
        if not text:
            continue
        sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip()
        if len(sentence) > 220:
            sentence = sentence[:220].rsplit(" ", 1)[0] + "…"
        parts.append(f"{sentence} [{index}]")
    return " ".join(parts)


def answer_question(query: str, paper_ids: Optional[Sequence[str]] = None, section_names: Optional[Sequence[str]] = None,
                    top_k: Optional[int] = None, mode: Optional[str] = None,
                    retrieved_chunks: Optional[Sequence[Dict[str, Any]]] = None,
                    retrieval_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Answer ``query`` from the indexed papers.

    ``status`` is one of: ``answered`` | ``insufficient_evidence`` | ``llm_unavailable`` | ``evidence_only``.
    Evidence is always returned so the user can verify or read the sources even if generation fails.
    """
    if retrieved_chunks is None:
        retrieval = search_chunks(query, top_k=min(top_k or settings.default_top_k, 5), mode=mode, paper_ids=paper_ids, section_names=section_names)
    else:
        retrieval = {
            "results": list(retrieved_chunks),
            "returned": len(retrieved_chunks),
            "mode": (mode or settings.retrieval_mode).lower(),
            "embedding_backend": (retrieval_metadata or {}).get("embedding_backend", "unknown"),
            "vector_store": (retrieval_metadata or {}).get("vector_store", "unknown"),
            "warnings": (retrieval_metadata or {}).get("warnings", []),
        }
    evidence = select_evidence(retrieval["results"])
    chat_llm = get_chat_llm(llm)
    base: Dict[str, Any] = {"query": query, "evidence": _evidence_payload(evidence), "retrieved_count": retrieval["returned"],
                            "retrieval": {"mode": retrieval["mode"], "embedding_backend": retrieval["embedding_backend"],
                                          "vector_store": retrieval["vector_store"], "warnings": retrieval["warnings"]},
                            "generation": {"backend": chat_llm.backend, "model": chat_llm.info()["model"]}}
    if not evidence:
        return {**base, "status": "insufficient_evidence", "answer": INSUFFICIENT + " No sufficiently relevant passages were found in the selected papers.",
                "grounded": False, "citations_used": []}
    if not chat_llm.configured:
        text = _extractive_cited_answer(evidence)
        cited = list(range(1, min(len(evidence), 3) + 1))
        return {**base, "status": "answered", "answer": text, "grounded": True, "citations_used": cited,
                "generation": {"backend": "extractive", "model": None, "fallback_used": True},
                "warnings": ["No language model is configured; showing an extractive cited answer from retrieved evidence."]}
    try:
        # Preserve the fast existing QA budget; Gemini gets a separate cloud timeout.
        using_gemini = bool(settings.gemini_api_key)
        qa_timeout = float(settings.gemini_timeout_seconds) if using_gemini else min(float(settings.llm_qa_timeout_seconds), 5.0)
        qa_max_tokens = min(settings.gemini_qa_max_tokens, 512) if using_gemini else min(settings.llm_qa_max_tokens, 100)
        text, generation = chat_llm.chat_with_info(
            build_messages(query, evidence), max_tokens=qa_max_tokens, timeout_seconds=qa_timeout,
        )
    except LLMUnavailable as exc:
        text = _extractive_cited_answer(evidence)
        cited = list(range(1, min(len(evidence), 3) + 1))
        return {**base, "status": "answered", "answer": text, "grounded": True, "citations_used": cited,
                "generation": {"backend": "extractive", "model": chat_llm.info()["model"], "fallback_used": True},
                "warnings": [f"{exc.public_message} Showing an extractive cited answer from retrieved evidence."]}
    cited = sorted({int(n) for n in _CITE_RE.findall(text) if 1 <= int(n) <= len(evidence)})
    invalid = {int(n) for n in _CITE_RE.findall(text)} - set(range(1, len(evidence) + 1))
    refused = INSUFFICIENT.lower() in text.lower()
    out = {**base, "status": "insufficient_evidence" if refused else "answered", "answer": text,
           "grounded": bool(cited) and not refused, "citations_used": cited, "generation": generation}
    if generation.get("warning"):
        out["warnings"] = [str(generation["warning"])]
    if invalid:
        out.setdefault("warnings", []).append(f"The model cited non-existent passages: {sorted(invalid)}.")
    if not refused and not cited:
        out.setdefault("warnings", []).append("The answer contains no citations; treat it as unverified.")
    return out
