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
| RAG with citations (OpenAI-compatible LLM, default Qwen3.5-9B) | Implemented, tested with fake LLM; no real Qwen call made |
| LED summarisation (windowed) + extractive fallback + ROUGE | Implemented; windowing logic tested with stubs; LED generation not run |
| Pairwise comparison and multi-paper insights | Implemented, tested |
| BGE-M3 fine-tuning + baseline/fine-tuned evaluation | Tooling implemented and unit-tested; **training not run, no results** |
| FastAPI endpoints, validation, error handling | Implemented, tested (131 backend tests) |
| React frontend (upload progress, QA with citations, summaries, compare, insights) | Implemented; typecheck, build, 11 tests, live client↔API test |
| Vercel / production deployment | Deployment-ready config; **not deployed** |
