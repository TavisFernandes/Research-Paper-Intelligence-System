# Project Status

See `IMPLEMENTATION_REPORT.md` for the detailed, verified status. Summary:

| Area | Status |
|---|---|
| PDF ingestion (PyMuPDF, OCR fallback, encrypted/corrupt/empty handling, dedup) | Implemented, tested (OCR engine itself mocked; EasyOCR not installed in test env) |
| spaCy preprocessing, section detection, hierarchical chunking | Implemented, tested |
| NER (rules + spaCy ORG; SciSpaCy optional) and TF-IDF keywords | Implemented, tested (SciSpaCy not run) |
| Dense (BGE-M3) / sparse (BM25) representations | Implemented; BGE-M3 weights not downloadable in test env, so semantic quality unverified |
| Redis vector store (RediSearch HNSW/FLAT KNN) | Implemented; protocol tested against a fake server and plain Redis; **not run against Redis Stack** |
| Hybrid retrieval, ranking, evidence gating | Implemented, tested |
| RAG with citations (Qwen3.5 cloud primary, Qwen3 8B local fallback) | Implemented; cloud primary and fallback behavior covered by mocked tests. QA reuses the search retrieval result, limits generated answers to 320 tokens, and applies a 16-second timeout to the primary request. The local fallback keeps its configured 300-second timeout. The current local `.env` has no cloud API key, so the live app uses the local fallback; no real cloud generation was verified. |
| LED summarisation (windowed) + extractive fallback + ROUGE | Implemented; windowing logic tested with stubs; LED generation not run |
| Pairwise comparison and multi-paper insights | Implemented, tested |
| BGE-M3 fine-tuning + baseline/fine-tuned evaluation | Tooling implemented and unit-tested; **training not run, no results** |
| FastAPI endpoints, validation, error handling | Implemented; current focused API, RAG, and LLM regression tests pass (59 tests). |
| React frontend (upload progress, QA with citations, summaries, compare, insights) | Implemented; prior typecheck, build, 11 tests, and live client↔API test passed. |
| Vercel / production deployment | Deployment-ready config; **not deployed** |

## Recent response-latency and fallback updates

- Chat shows retrieved passages while answer generation is underway and reuses the server-held search result for QA, avoiding a second retrieval pass.
- QA generation is capped at `LLM_QA_MAX_TOKENS=320`. The cloud primary uses `LLM_QA_TIMEOUT_SECONDS=16`; when it is unavailable or the key is missing, QA retains the configured local model fallback (`qwen3:8b`, with `LLM_FALLBACK_TIMEOUT_SECONDS`, currently 300 seconds).
- `/api/health` reports when the cloud key is missing and chat is using the configured fallback. With the current blank cloud key, local fallback generation is expected and may be slow on CPU; a sub-20-second local answer is not guaranteed.
- No sample paper was added to live memory or the vector store. Regression tests used isolated test fixtures.
- Latest verification: 59 focused backend tests passed; `git diff --check` passed. Pylance found no diagnostics in the touched RAG/provider files. No authenticated cloud model request or production deployment has been verified.
