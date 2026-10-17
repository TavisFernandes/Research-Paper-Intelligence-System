# Implementation Report

Scope: complete, debug and harden the existing project against the ATML Project Pipeline PDF. The existing structure (FastAPI backend, Vite/React frontend, `Model_Training/`) was kept; the backend was largely rewritten because most pipeline stages were stubs or had defects.

## 1. Audit of the original code — defects found and fixed

| Original problem | Fix |
|---|---|
| `list_papers()` globbed `P-*.json` but ids were `P001` → library always empty; id collisions possible | Unified listing, collision-safe `next_paper_id()` (also respects in-flight uploads); regression test |
| Paper ids from URLs were used in file paths (path traversal risk) | Strict id validation (`^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`), atomic writes |
| "Redis store" had no vector search (hash + in-process scan) | Real RediSearch index (HNSW/FLAT, COSINE), KNN with paper/section pre-filters, dimension/model metadata, upsert-idempotent, delete, health, reset |
| Silent fallback to in-memory store | `VECTOR_STORE_BACKEND=auto|redis|memory`; fallback is reported in `/api/health`, UI badge and search warnings; `redis` mode raises a clear 503 |
| Hashing embeddings (384-d) mixed with BGE-M3 (1024-d) in one index | Embedder reports `backend`/`semantic`; index stores its dimension and rejects mismatches with reindex instructions |
| Section detection: exact-match headings only, no hierarchy, `data`/`analysis` over-matched | Numbered/Roman/ALL-CAPS/letter-spaced/inline headings, containment rules only for numbered or caps headings, subsection hierarchy, `OTHER` only for in-sequence numbered headings, `UNKNOWN` preamble, page spans |
| Chunker: duplicate chunk ids for repeated sections, mid-word overlap, section-wide page range per chunk | Sentence-aware chunks, whole-sentence overlap, word-boundary splitting of long sentences, per-chunk page ranges, unique deterministic ids |
| NER regex matched any capitalised word as DATASET | Gazetteers + cue patterns + spaCy ORG (filtered); SciSpaCy used when installed; each entity has `source` |
| Dehyphenation regex destroyed real compounds; lemmatizer produced "runn" | Line-break-only dehyphenation; improved fallback lemmas; spaCy lemmatizer on pre-tokenised text |
| No handling of corrupt/encrypted/empty PDFs; OCR on every low-text page | Clean `PdfIngestionError`s; OCR only for low-text pages that contain images; `ocr_unavailable`/`ocr_failed` flagged per page; blank pages marked `empty` |
| LED summariser truncated to first 60,000 chars and rebuilt the pipeline per call | Cached model, token-aware sentence windows + map-reduce (no silent truncation), extractive fallback labelled as such |
| RAG returned retrieved text as an "answer" when no LLM | Evidence-gated prompt, citation validation, `insufficient_evidence` without calling the LLM, `evidence_only`/`llm_unavailable` statuses, timeouts mapped to 503-style messages |
| Comparison = cosine similarity of section text | 10-dimension evidence table with section/page provenance, entity overlap, reported vs inferred separation, optional labelled LLM narrative; multi-paper insights |
| Training script had no negatives/eval/split | Pair construction with BM25 hard negatives, group-wise split, MNRL/GradCache trainer, baseline-vs-finetuned comparison on identical data, metrics |
| Frontend: static placeholder panels (Methods/Findings), single-file upload, Replit-only Vite config (required `PORT`/`BASE_PATH`), Windows-only devDependencies that break Linux/Vercel installs | Data-driven UI (see §3); portable Vite config; removed Replit plugins and win32 packages; regenerated lockfile; `vercel.json` |

## 2. Feature status vs. the PDF pipeline

| Stage | Status |
|---|---|
| PyMuPDF extraction, page data (`paper_id, page_number, extraction_method, raw_text`) | Done, tested |
| EasyOCR fallback | Code done; engine **not installed/run here** (tests mock `_ocr_page`; "unavailable" path tested for real) |
| spaCy cleaning / sentences / tokens / lemmas | Done, tested with `en_core_web_sm` |
| Rule-based section detection + hierarchy | Done, tested |
| Hierarchical chunking (configurable size/overlap) | Done, tested |
| SciSpaCy NER | Optional path coded; **not run** (model not installable here). Rule + spaCy NER run and are tested |
| BGE-M3 dense + sparse | Coded (FlagEmbedding → sentence-transformers); **not run** (Hugging Face unreachable here). TF-IDF keywords and BM25 sparse retrieval run and are tested |
| Redis vector store | Coded for Redis Stack; protocol/commands tested against a fake server; error paths tested against a real plain-Redis 7.0 server; **KNN on a real Redis Stack not executed** |
| Retrieval + ranking (dense/lexical/hybrid RRF, top-k, filters, evidence gating) | Done, tested (with hashing embeddings) |
| LangChain orchestration | Implemented as an explicit thin chain (no LangChain dependency); same stages |
| RAG with Qwen3.5-9B | OpenAI-compatible provider; **no real Qwen call made**; tested with fakes, unreachable endpoint and simulated timeout |
| LED summarisation | Windowing/map-reduce logic tested with stubs; **LED generation not run** (no torch/weights). Extractive fallback tested |
| ROUGE-1/2/L | Done, tested on known strings; no corpus-level scores were produced here |
| Pairwise comparison, multi-paper insights | Done, tested (incl. "no number appears that is not in the papers") |
| BGE-M3 fine-tuning + Recall@5/10, MRR@10, nDCG@10 | Tooling done and unit-tested (data build, split leakage, metrics with known values, baseline-vs-finetuned harness with stub encoders). **Training was not run; there are no fine-tuning results** |
| LED fine-tuning | Existing notebook retained; ROUGE values in `LED_evaluation_results.csv` are the team's, not reproduced |
| FastAPI endpoints | Done, tested via `TestClient` incl. error paths |
| React frontend | Done; typecheck, production build, component tests, live client↔API test |
| Vercel/HTTPS deployment | Config only; **not deployed** |

## 3. Frontend changes
Library loaded from the API (persisted, not session-only); multi-file upload with per-file progress/stage/failure messages; overview (sections, entities, keywords, warnings); paper and section summaries; evidence-backed Q&A showing paper, section, page and excerpt, with explicit insufficient-evidence / evidence-only / LLM-unavailable states; pair picker + comparison table with provenance and reported/inferred/generated tags; multi-paper insights; backend health badge. Framework kept as Vite+React (the project's existing choice; deployable to Vercel as a static site) rather than migrating to Next.js.

## 4. Test results (actually run)

| Command | Result |
|---|---|
| `cd backend && pytest -q` (fresh venv from `requirements-dev.txt` + spaCy model) | **131 passed, 1 skipped** (the live-Redis test) |
| `REDIS_TEST_URL=redis://localhost:6399 pytest -q` (real Redis 7.0.15, no RediSearch) | **132 passed** (live test verifies the "RediSearch missing" path) |
| `ruff check . --select E9,F,B --ignore B008,B905` | clean |
| `pnpm --filter … run typecheck` / `build` | clean / built (`vite build`, ~500 kB JS) |
| `pnpm --filter … run test` | **11 passed** (API client, Upload/Chat/Compare components) |
| Same, with `VITE_API_BASE_URL` + two PDFs against a live `uvicorn` | **12 passed** (upload → ingest → QA → summarise → compare → insights → error path) |
| `pnpm install --frozen-lockfile` from a clean tree | OK |
| CORS preflight against the live API | allowed origin accepted; other origin rejected (400) |

Covered edge cases: corrupt, truncated, empty, encrypted, blank and scanned PDFs; non-PDF/empty/oversized uploads; duplicate uploads; path-traversal ids; Redis down / plain Redis / dimension mismatch; missing LLM key; LLM timeout/unreachable; hallucinated citations; empty retrieval; irrelevant queries; unexpected 500s not leaking internals.

### Not run (and why)
* **Real BGE-M3 / LED / Qwen / EasyOCR / SciSpaCy:** the sandbox cannot reach Hugging Face or the SciSpaCy host and has no GPU/torch.
* **Redis Stack KNN, `docker compose`:** no Docker and no RediSearch module available.
* **BGE-M3 fine-tuning and PubMedQA download:** needs HF access and GPU.
* **Browser E2E, Vercel deployment:** no browser/credentials.
* mypy / full static typing of the Python code was not run.

## 5. Known limitations
* Without BGE-M3, retrieval is BM25-driven (hashing "embeddings" are not semantic). `MIN_DENSE_SCORE=0.35` is a starting value for BGE-M3 cosine and should be tuned on your data.
* Section/dimension extraction is rule-based: unusual layouts, two-column interleaving, or papers without standard headings give coarser sections (`UNKNOWN`) and "not identified" cells.
* Ingestion jobs are tracked in memory and run in-process (single worker; status lost on restart; stored papers are not).
* BM25 index is rebuilt in-process from the store when the chunk count changes (fine for hundreds of papers, not millions).
* PubMedQA-derived pairs are constructed (see README); gains may not transfer outside biomedicine.
* LED on CPU with long inputs is slow; the repo's `.pth` is an LFS pointer, not weights.
* No authentication/rate limiting on the API; add a gateway before exposing it publicly.
