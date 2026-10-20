# Research Paper Intelligence & Comparison System

Upload research-paper PDFs, then search them, ask questions with page-level citations, read paper/section summaries, compare two papers across ten dimensions and get multi-paper insights. Implements the ATML pipeline:

```
PDFs → PyMuPDF (+EasyOCR for scanned pages) → page data → spaCy preprocessing → rule-based section detection
     → hierarchical chunks (paper→page→section→chunk) → NER + TF-IDF → BGE-M3 dense (+BM25 sparse) → Redis vector store
     → hybrid retrieval → RAG (Gemini cloud API, local fallback) │ LED summarisation → pairwise comparison → multi-paper insights
```

* **Backend:** FastAPI (`backend/`) · **Frontend:** React + Vite (`frontend/`, deployable on Vercel) · **Vector DB:** Redis Stack (RediSearch)
* See **`IMPLEMENTATION_REPORT.md`** for exactly what was implemented, what was tested, and what could **not** be verified.

## Quick start (no GPU, no API keys, ~5 minutes)

```bash
git clone <repo> && cd <repo>
cp .env.example .env                       # optional; defaults work

# 1. Backend (Python 3.10+)
scripts/setup_backend.sh                   # venv + core deps + spaCy model   (add "dev" for test tools)
docker compose up -d redis                 # Redis Stack with persistence (recommended)
scripts/start_backend.sh                   # http://localhost:8000  (interactive docs: /docs)

# 2. Frontend (Node 20+, pnpm)
scripts/start_frontend.sh                  # http://localhost:5173 -> open /console
```

Without Docker/Redis the API falls back to a **non-persistent in-memory store** (reported in `/api/health` and in the UI badge). When the local fine-tuned checkpoint is present, it is selected automatically, but it needs the ML dependencies and the `BAAI/bge-m3` base model on first use. Without those dependencies the API uses **non-semantic hashing embeddings** plus BM25, so retrieval is lexical-driven. Both fallbacks are always reported, never silent. Configure a cloud LLM API key to generate answers; without one, chat returns the retrieved evidence and a clear configuration error rather than waiting on the slow local answer model.

### Enable the real models (optional, needs internet + disk)

```bash
scripts/setup_backend.sh ml                # torch, transformers, sentence-transformers, FlagEmbedding, EasyOCR
```

| Capability | How to enable | Notes |
|---|---|---|
| BGE-M3 dense (+ sparse weights) | install `requirements-ml.txt` (first use downloads the `BAAI/bge-m3` base encoder, ~2.3 GB) | When `Model_Training/BGE_M3_Model/bge_m3_finetuned.pth` exists, it is selected by default and loaded on top of the base encoder using the notebook's mean pooling. GPU is used automatically if CUDA is available. **Changing the model changes the vector dimension/space; rebuild with `POST /api/reindex {"reset": true}` before searching.** |
| OCR for scanned PDFs | `pip install easyocr` | Only pages with no/little text *and* images are OCR'd. Without EasyOCR such pages are flagged `ocr_unavailable`. |
| SciSpaCy NER | `pip install scispacy` + a model wheel from the [SciSpaCy releases](https://github.com/allenai/scispacy#available-models) (e.g. `en_core_sci_sm`) | Without it, entities come from rules (+ spaCy `ORG`). Every entity records its `source`. |
| LED summarisation | `ENABLE_LED=true` (+ ML extras) | Otherwise extractive summaries are returned, labelled `backend: "extractive"`. |
| Grounded answers | Set `GEMINI_API_KEY` in `.env` | Gemini is used only for chat answers; the existing `LLM_*` provider remains unchanged for paper comparisons. Chat falls back to the configured local model when Gemini is unavailable. Use `GEMINI_MODEL` to select another Gemini model (default: `gemini-3.1-flash-lite`); Gemini chat defaults to a 30-second timeout and a 512-token output budget. |

## Configuration

All settings are environment variables; see `.env.example` (documented). Secrets (`GEMINI_API_KEY` and `LLM_API_KEY`) are only read from the environment, never logged or returned.

## API (FastAPI, docs at `/docs`)

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Component status (Redis/RediSearch, embeddings, LLM, LED, OCR, spaCy) + warnings |
| `POST /api/papers/upload` | Multipart `files` (one or many PDFs) → `202` with one job per file; duplicates (same SHA-256) are not re-ingested |
| `GET /api/ingestion/{job_id}` · `GET /api/papers/{id}/status` | Ingestion status/progress/stage/error |
| `GET /api/papers` · `GET /api/papers/{id}` · `DELETE /api/papers/{id}` | List / full paper (pages, sections, chunks, analysis) / delete incl. vectors |
| `POST /api/papers/{id}/reindex` · `POST /api/reindex` | Rebuild vectors (`{"reset":true}` drops the Redis index first) |
| `POST /api/search` | Ranked chunks (`dense` / `lexical` / `hybrid`), filters, `top_k`, evidence flag |
| `POST /api/qa` | RAG answer + evidence; `status` ∈ `answered`, `insufficient_evidence`, `evidence_only`, `llm_unavailable`; the chat may pass the one-use, 60-second `retrieval_id` returned by `/api/search` to reuse server-held results |
| `POST /api/summarize` | Paper summary + per-section summaries, or one `section_name` |
| `POST /api/compare` | Two-paper structured comparison table (reported vs inferred are separated) |
| `POST /api/insights` | Multi-paper insights (≥2 papers) |
| `POST /api/evaluate/retrieval` | Recall@5/10, MRR@10, nDCG@10 of the live index for labelled queries |
| `POST /api/evaluate/summarization` | ROUGE-1/2/L from predictions+references, or a generated summary vs a reference |

Errors: `400` invalid input · `404` unknown paper/job · `422` validation · `503` Redis/embedding/LLM unavailable (clear message) · `500` generic message (details only in server logs).

## How evidence is kept honest

* Retrieval returns a `supported` flag: dense cosine ≥ `MIN_DENSE_SCORE` (only trusted for semantic embeddings) **or** ≥ `MIN_LEXICAL_COVERAGE` of query terms present. Unsupported chunks are dropped by default, so irrelevant text is never shown as evidence, and the LLM is **not called** when nothing relevant is retrieved.
* The prompt restricts the model to numbered passages and requires citations; citations to non-existent passages or answers without citations are flagged in `warnings`.
* Comparison/insight cells are verbatim sentences with section + page. Overlaps and similarity scores are labelled **inferred**; LLM prose (optional) is labelled **generated**. Missing information is "not reported / not identified", never invented. No publication years are extracted, so no temporal "trends" are claimed.

## Redis

`docker-compose.yml` runs `redis/redis-stack-server` with `--appendonly yes` and a named volume, so vectors survive restarts. Index: HNSW (`REDIS_INDEX_ALGORITHM=FLAT` also supported), COSINE, `DIM` taken from the embedder; the dimension is stored and validated. Plain Redis (no RediSearch) is detected and reported with instructions. On start-up the API re-indexes any stored paper that is missing from the store (e.g. after a flush). Persistence is a *server* property; `/api/health` reports whether AOF is on.

## Fine-tuning BGE-M3 and evaluating retrieval

```bash
pip install -r backend/requirements-training.txt
cd backend
python -m training.bge_m3.prepare_pubmedqa --config pqa_labeled --out data/bge_m3        # builds query/positive/negatives, group-wise train/val split
python -m training.bge_m3.finetune --train data/bge_m3/train.jsonl --val data/bge_m3/validation.jsonl \
       --output checkpoints/bge-m3-sci --freeze-embeddings --cached-mini-batch 8 --gradient-checkpointing --bf16
python -m training.bge_m3.compare --eval data/bge_m3/validation.jsonl --baseline BAAI/bge-m3 --finetuned checkpoints/bge-m3-sci/final
# Then select the saved model with EMBEDDING_MODEL and POST /api/reindex {"reset": true}.
```

**Read this before citing results:** PubMedQA has questions + abstract paragraphs + answers, *not* retrieval labels. Pairs are *constructed* (question → its abstract; negatives = other questions' abstracts, BM25-mined + random). That measures adaptation to biomedical question→abstract matching, not human-judged passage relevance in full papers, and a PubMedQA-tuned model may not transfer to other fields. Use `--granularity paragraph` only if you accept weak labels. The objective is InfoNCE (`MultipleNegativesRankingLoss`, optionally GradCache); only the dense head is tuned. The local `Model_Training/BGE_M3_Model/bge_m3_finetuned.pth` checkpoint is a PyTorch state dict trained on the `BAAI/bge-m3` encoder and is loaded by the application when present.

LED: `Model_Training/LED_Model/LED_Training.ipynb` is the team's LED-Base fine-tuning notebook (PubMed summarisation, 4096-token inputs, 3 epochs). `LED_evaluation_results.csv` in that folder records ROUGE-1 32.76 / ROUGE-2 10.10 / ROUGE-L 17.80 from that notebook run — *recorded by the team, not reproduced here*. The `.pth` in the repo is a Git-LFS pointer (no weights). To use your own checkpoint set `LED_MODEL` (HF-format dir) or `LED_STATE_DICT_PATH`, and match the training length (`LED_MAX_INPUT_TOKENS=4096`, `LED_WINDOW_TOKENS≈3500`). Evaluate with `python -m training.led.evaluate_checkpoint val.jsonl`.

## Tests

```bash
scripts/setup_backend.sh dev && scripts/run_tests.sh                    # ruff + pytest (131 tests)
REDIS_TEST_URL=redis://localhost:6379/0 scripts/run_tests.sh            # + live-Redis test (full KNN path needs Redis Stack)
cd frontend && pnpm install && pnpm --filter @workspace/research-paper-intelligence run typecheck
pnpm --filter @workspace/research-paper-intelligence run test           # 11 unit/component tests
# frontend client ↔ live backend integration (start the API first):
VITE_API_BASE_URL=http://127.0.0.1:8000 API_TEST_PDFS=/path/a.pdf,/path/b.pdf pnpm --filter @workspace/research-paper-intelligence run test
```

## Deployment

**Backend (HTTPS):** `docker compose up -d --build` runs Redis Stack + API on port 8000 (`--build-arg INSTALL_ML=1` in `backend/Dockerfile` bakes in the ML stack; GPU hosts need a CUDA torch build). Put it behind a TLS proxy (Caddy, nginx, Fly.io, Render, Railway, a cloud LB). Set `CORS_ALLOW_ORIGINS=https://<your-vercel-domain>` (comma-separated). Mount persistent volumes for Redis and `PAPER_STORAGE_DIR`. Run a single API worker per volume (job status is in-memory).

**Frontend on Vercel:** import the repo, set **Root Directory = `frontend`**; `frontend/vercel.json` supplies install/build/output/SPA rewrite. Add the env var `VITE_API_BASE_URL=https://<your-backend>` (build-time) and redeploy. Or: `cd frontend && npx vercel --prod`.

*This repository has not been deployed by the authors of this change; the steps above are untested against a live Vercel/host account.*

## Repository layout

```
backend/   api/ (FastAPI) · pdf_processing/ · nlp/ · embeddings/ · vector_store/ · retrieval/ · rag/ · llm/
           summarization/led/ · comparison/ · ingestion/ · training/{bge_m3,led}/ · tests/
frontend/  artifacts/research-paper-intelligence (React + Vite app) · vercel.json
Model_Training/LED_Model/   team's LED notebook, results CSV, LFS pointer
docker-compose.yml · .env.example · scripts/
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| UI badge "Backend offline" | start the API; set `VITE_API_BASE_URL` (or use the dev proxy); check `CORS_ALLOW_ORIGINS` |
| `Redis is reachable but the RediSearch module is missing` | use `redis/redis-stack-server` (compose file), not plain `redis` |
| `index was built with N-d vectors` | embedding model changed → `POST /api/reindex {"reset": true}` |
| `spaCy model missing` | `python -m spacy download en_core_web_sm` |
| Scanned PDF shows no text | `pip install easyocr`; check `/api/health` → `ocr` |
| Answers show "evidence only" | set `LLM_BASE_URL` / `LLM_API_KEY` |
| Weak retrieval, warning "non-semantic hashing" | install ML extras so BGE-M3 loads |
| First request is slow | models load lazily once per process (BGE-M3 ~2 GB) |
