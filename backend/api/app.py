"""FastAPI application: ingestion, retrieval, RAG, summaries, comparison, insights and evaluation."""
from __future__ import annotations

import logging
import secrets
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Sequence

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from comparison import compare_papers, research_insights
from config import settings
from embeddings import get_embedder
from errors import AppError, InvalidInputError, PaperNotFoundError
from ingestion.indexing import index_paper, sync_index
from ingestion.jobs import jobs
from ingestion.service import register_upload, run_ingestion
from llm import get_chat_llm, llm
from models import (AnswerRequest, CompareRequest, HealthResponse, InsightsRequest, ReindexRequest, RetrievalEvalRequest,
                    SearchRequest, SummarizationEvalRequest, SummaryRequest)
from nlp import ner_status
from pdf_processing.pdf import ocr_available
from pdf_processing.preprocess import nlp_status
from pdf_processing.storage import delete_paper, list_papers, load_paper, save_paper, validate_paper_id
from rag import answer_question
from retrieval import invalidate_lexical_index, search_chunks
from summarization.led import led_status, rouge, summarize_paper
from training.bge_m3.evaluate import evaluate_rankings
from vector_store import get_vector_store

logger = logging.getLogger("paperintel")
_sync_state: Dict[str, Any] = {"state": "pending"}
_retrieval_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
_retrieval_cache_lock = threading.Lock()
_RETRIEVAL_CACHE_TTL_SECONDS = 60
_RETRIEVAL_CACHE_MAX_ENTRIES = 128


def _cache_search_result(request: SearchRequest, result: Dict[str, Any]) -> str:
    retrieval_id = secrets.token_urlsafe(24)
    now = time.monotonic()
    entry = {
        "query": request.query,
        "paper_ids": tuple(sorted(set(request.paper_ids or []))),
        "section_name": request.section_name,
        "mode": result["mode"],
        "top_k": request.top_k,
        "include_low_confidence": request.include_low_confidence,
        "result": result,
    }
    with _retrieval_cache_lock:
        expired = [key for key, (created, _) in _retrieval_cache.items() if now - created > _RETRIEVAL_CACHE_TTL_SECONDS]
        for key in expired:
            _retrieval_cache.pop(key, None)
        while len(_retrieval_cache) >= _RETRIEVAL_CACHE_MAX_ENTRIES:
            oldest = min(_retrieval_cache, key=lambda key: _retrieval_cache[key][0])
            _retrieval_cache.pop(oldest)
        _retrieval_cache[retrieval_id] = (now, entry)
    return retrieval_id


def _take_cached_search_result(retrieval_id: str, request: AnswerRequest) -> Dict[str, Any] | None:
    with _retrieval_cache_lock:
        cached = _retrieval_cache.pop(retrieval_id, None)
    if cached is None or time.monotonic() - cached[0] > _RETRIEVAL_CACHE_TTL_SECONDS:
        return None
    entry = cached[1]
    if (
        entry["query"] != request.query
        or entry["paper_ids"] != tuple(sorted(set(request.paper_ids or [])))
        or entry["section_name"] != request.section_name
        or entry["mode"] != (request.mode or settings.retrieval_mode)
        or entry["top_k"] < request.top_k
        or entry["include_low_confidence"] != request.include_low_confidence
    ):
        return None
    return entry["result"]


def _background_sync() -> None:
    _sync_state["state"] = "running"
    try:
        _sync_state.update({"state": "done", **sync_index()})
    except Exception as exc:  # never block startup on indexing problems
        logger.exception("Start-up index synchronisation failed")
        _sync_state.update({"state": "failed", "error": type(exc).__name__})
    # Load BGE once in the background so the first compare/search is not a 20s+ cold start.
    try:
        embedder = get_embedder()
        embedder.encode("warmup")
        logger.info("Embedding warmup complete (%s)", embedder.backend)
    except Exception:
        logger.exception("Embedding warmup failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    threading.Thread(target=_background_sync, daemon=True, name="index-sync").start()
    yield


app = FastAPI(title="Research Paper Intelligence API", version="2.0.0", lifespan=lifespan,
              description="Ingest research PDFs, retrieve evidence, answer questions with citations, summarise and compare papers.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.allow_origins.split(",") if o.strip()],
                   allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------------ error handling
@app.exception_handler(AppError)
async def _app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.public_message})


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Invalid request.", "errors": fields})


@app.exception_handler(Exception)
async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


def _paper_or_404(paper_id: str) -> Dict[str, Any]:
    validate_paper_id(paper_id)
    paper = load_paper(paper_id)
    if not paper:
        raise PaperNotFoundError(f"Paper '{paper_id}' not found.")
    return paper


def _papers_or_404(paper_ids: Sequence[str]) -> List[Dict[str, Any]]:
    unique = list(dict.fromkeys(paper_ids))
    return [_paper_or_404(pid) for pid in unique]


def _summary_row(paper: Dict[str, Any]) -> Dict[str, Any]:
    chunk_count = len(paper.get("chunks", []))
    return {"paper_id": paper["paper_id"], "filename": paper.get("filename"), "title": paper.get("title"), "total_pages": paper.get("total_pages"),
            "status": paper.get("status", "processed"), "chunk_count": chunk_count,
            "sections": sorted({s["section_name"] for s in paper.get("sections", [])}),
            "keywords": [k["keyword"] for k in paper.get("analysis", {}).get("keywords", [])[:8]],
            "analysis": paper.get("analysis"), "indexing": paper.get("indexing"), "created_at": paper.get("created_at")}


# ------------------------------------------------------------------------- health
@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    store = get_vector_store()
    store_health = store.health()
    embedder = get_embedder()
    chat_llm = get_chat_llm()
    warnings: List[str] = []
    if store.backend == "memory":
        warnings.append(store_health.get("degraded_reason") or "Using the in-memory vector store (not persistent).")
    if embedder.backend == "hashing":
        warnings.append("Embeddings are a non-semantic hashing fallback.")
    if not chat_llm.configured and not llm.configured:
        warnings.append("No LLM configured: question answering returns evidence only.")
    if settings.llm_base_url and settings.llm_model and not settings.llm_api_key and not settings.gemini_api_key:
        warnings.append("The cloud LLM API key is missing; chat uses the configured local fallback. Set LLM_API_KEY to enable cloud answers.")
    if not settings.enable_led:
        warnings.append("LED summarisation is disabled; extractive summaries are used.")
    if not ocr_available():
        warnings.append("EasyOCR is not installed; scanned pages cannot be read.")
    if nlp_status()["backend"].startswith(("blank", "unavailable")):
        warnings.append("spaCy model missing: " + str(nlp_status()["setup_hint"]))
    components = {"vector_store": store_health, "embeddings": embedder.status(), "llm": llm.info(), "chat_llm": chat_llm.info(), "summarization": led_status(),
                  "nlp": nlp_status(), "ner": ner_status(), "ocr": {"available": ocr_available(), "enabled": settings.ocr_enabled},
                  "index_sync": dict(_sync_state), "papers": len(list_papers())}
    degraded = bool(store_health.get("connected") is False) or store.backend == "memory" and settings.vector_store_backend == "redis"
    return HealthResponse(status="degraded" if degraded or warnings else "ok", components=components, warnings=warnings)


# --------------------------------------------------------------------- ingestion
@app.post("/api/papers/upload", status_code=202, tags=["ingestion"])
async def upload_papers(background: BackgroundTasks, files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    """Upload one or more PDFs. Processing runs in the background; poll ``/api/ingestion/{job_id}``."""
    accepted, rejected = [], []
    for upload in files:
        name = upload.filename or "upload.pdf"
        content = await upload.read(settings.max_upload_bytes + 1)
        try:
            job = register_upload(name, content)
        except InvalidInputError as exc:
            rejected.append({"filename": name, "status": "rejected", "error": exc.public_message})
            continue
        if job.status == "queued":
            background.add_task(run_ingestion, job.job_id)
        accepted.append(job.to_dict())
    if not accepted:
        raise HTTPException(status_code=400, detail=rejected[0]["error"] if len(rejected) == 1 else "No valid PDF files were uploaded.")
    return {"jobs": accepted, "rejected": rejected}


@app.get("/api/ingestion/{job_id}", tags=["ingestion"])
def ingestion_status(job_id: str) -> Dict[str, Any]:
    job = jobs.get(job_id)
    if not job:
        raise PaperNotFoundError("Unknown ingestion job.")
    return job.to_dict()


@app.get("/api/papers/{paper_id}/status", tags=["ingestion"])
def paper_status(paper_id: str) -> Dict[str, Any]:
    validate_paper_id(paper_id)
    job = jobs.for_paper(paper_id)
    paper = load_paper(paper_id)
    if job and job.status in ("queued", "processing", "failed"):
        return job.to_dict()
    if paper:
        return {"paper_id": paper_id, "status": "completed", "stage": "done", "progress": 100, "indexing": paper.get("indexing")}
    raise PaperNotFoundError(f"Paper '{paper_id}' not found.")


@app.get("/api/papers", tags=["papers"])
def papers() -> List[Dict[str, Any]]:
    return [_summary_row(p) for p in list_papers()]


@app.get("/api/papers/{paper_id}", tags=["papers"])
def get_paper(paper_id: str) -> Dict[str, Any]:
    return _paper_or_404(paper_id)


@app.delete("/api/papers/{paper_id}", tags=["papers"])
def remove_paper(paper_id: str) -> Dict[str, Any]:
    validate_paper_id(paper_id)
    if not delete_paper(paper_id):
        raise PaperNotFoundError(f"Paper '{paper_id}' not found.")
    removed = get_vector_store().delete_paper(paper_id)
    invalidate_lexical_index()
    return {"deleted": paper_id, "chunks_removed": removed}


@app.post("/api/papers/{paper_id}/reindex", tags=["papers"])
def reindex_paper(paper_id: str) -> Dict[str, Any]:
    paper = _paper_or_404(paper_id)
    paper["indexing"] = index_paper(paper)
    save_paper(paper)
    return {"paper_id": paper_id, "indexing": paper["indexing"]}


@app.post("/api/reindex", tags=["system"])
def reindex_all(request: ReindexRequest) -> Dict[str, Any]:
    """Rebuild the vector index (``reset=true`` drops a Redis index first, needed after changing the embedding model)."""
    store = get_vector_store()
    if request.reset and hasattr(store, "reset_index"):
        store.reset_index()  # type: ignore[attr-defined]
    count = 0
    for paper in list_papers():
        paper["indexing"] = index_paper(paper)
        save_paper(paper)
        count += 1
    return {"reindexed": count}


# ----------------------------------------------------------- retrieval / QA / summaries
@app.post("/api/search", tags=["retrieval"])
def search(request: SearchRequest) -> Dict[str, Any]:
    if request.paper_ids:
        _papers_or_404(request.paper_ids)
    sections = [request.section_name] if request.section_name else None
    result = search_chunks(request.query, request.top_k, request.mode, request.paper_ids, sections, request.include_low_confidence)
    return {**result, "retrieval_id": _cache_search_result(request, result)}


@app.post("/api/qa", tags=["rag"])
def question_answering(request: AnswerRequest) -> Dict[str, Any]:
    """Grounded answer with citations. ``status`` tells whether it was answered, insufficient, or LLM-unavailable."""
    if request.paper_ids:
        _papers_or_404(request.paper_ids)
    sections = [request.section_name] if request.section_name else None
    cached_result = _take_cached_search_result(request.retrieval_id, request) if request.retrieval_id else None
    if cached_result:
        _papers_or_404(list(dict.fromkeys(hit["paper_id"] for hit in cached_result["results"])))
    return answer_question(
        request.query, request.paper_ids, sections, request.top_k, request.mode,
        retrieved_chunks=cached_result["results"] if cached_result is not None else None,
        retrieval_metadata=cached_result if cached_result is not None else None,
    )


@app.post("/api/summarize", tags=["summaries"])
def summary(request: SummaryRequest) -> Dict[str, Any]:
    return summarize_paper(_paper_or_404(request.paper_id), request.section_name, request.max_sentences, request.per_section)


@app.post("/api/compare", tags=["comparison"])
def compare(request: CompareRequest) -> Dict[str, Any]:
    left, right = _papers_or_404(request.paper_ids)[:2] if len(set(request.paper_ids)) == 2 else (None, None)
    if left is None:
        raise InvalidInputError("Select two different papers to compare.")
    return compare_papers(left, right, use_llm=request.use_llm)


@app.post("/api/insights", tags=["comparison"])
def insights(request: InsightsRequest) -> Dict[str, Any]:
    return research_insights(_papers_or_404(request.paper_ids), use_llm=request.use_llm)


# ---------------------------------------------------------------------- evaluation
@app.post("/api/evaluate/retrieval", tags=["evaluation"])
def evaluate_retrieval(request: RetrievalEvalRequest) -> Dict[str, Any]:
    """Recall@5/10, MRR@10 and nDCG@10 of the *live* index for labelled queries."""
    rankings, relevant = [], []
    for item in request.queries:
        if not item.relevant_chunk_ids and not item.relevant_paper_ids:
            raise InvalidInputError("Every query needs relevant_chunk_ids or relevant_paper_ids.")
        result = search_chunks(item.query, 10, request.mode, request.paper_ids, include_low_confidence=True)
        by_paper = bool(item.relevant_paper_ids) and not item.relevant_chunk_ids
        rankings.append([r["paper_id"] if by_paper else r["chunk_id"] for r in result["results"]])
        relevant.append(set(item.relevant_paper_ids if by_paper else item.relevant_chunk_ids))
    return {"metrics": evaluate_rankings(rankings, relevant), "n_queries": len(rankings), "mode": request.mode or settings.retrieval_mode,
            "embedding_backend": get_embedder().backend}


@app.post("/api/evaluate/summarization", tags=["evaluation"])
def evaluate_summarization(request: SummarizationEvalRequest) -> Dict[str, Any]:
    """ROUGE-1/2/L. Provide predictions+references, or a paper_id plus a reference summary."""
    if request.predictions is not None or request.references is not None:
        if request.predictions is None or request.references is None:
            raise InvalidInputError("Provide both predictions and references.")
        return {"metrics": rouge(request.predictions, request.references), "source": "provided_predictions"}
    if request.paper_id and request.reference_summary:
        paper = _paper_or_404(request.paper_id)
        generated = summarize_paper(paper, request.section_name, per_section=False)
        if not generated.get("summary"):
            raise InvalidInputError("No summary could be generated for the selected paper/section.")
        return {"metrics": rouge([generated["summary"]], [request.reference_summary]), "source": "generated_summary",
                "backend": generated.get("backend"), "generated_summary": generated["summary"]}
    raise InvalidInputError("Provide predictions+references, or paper_id+reference_summary. ROUGE needs a valid reference summary.")
