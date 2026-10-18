# Backend

FastAPI service for ingestion, retrieval, RAG, summarisation, comparison and evaluation. See the root `README.md` for setup, API table and deployment.

```bash
pip install -r requirements-dev.txt && python -m spacy download en_core_web_sm
uvicorn main:app --reload --port 8000        # docs: http://localhost:8000/docs
pytest -q                                     # 131 tests, no network/GPU/models needed
```

## Module map

| Package | Responsibility |
|---|---|
| `config/` | env-driven `Settings` (no secrets in code) |
| `pdf_processing/` | `pdf.py` PyMuPDF + OCR fallback · `preprocess.py` spaCy cleaning/sentences/tokens/lemmas · `sections.py` heading detection · `chunks.py` sentence-aware chunks · `pipeline.py` orchestration · `storage.py` atomic JSON/PDF storage |
| `nlp/` | `ner.py` (SciSpaCy if installed, rules, spaCy ORG), `keywords.py` (TF-IDF) |
| `embeddings/` | cached BGE-M3 encoder (FlagEmbedding → sentence-transformers → opt-in hashing fallback) |
| `vector_store/` | `redis_store.py` (RediSearch HNSW/FLAT KNN + filters), `memory_store.py`, factory |
| `retrieval/` | BM25, dense/lexical/hybrid (RRF) search with evidence-support flags |
| `llm/`, `rag/` | OpenAI-compatible provider (timeouts, error mapping); retrieval → evidence selection → prompt → cited answer |
| `summarization/led/` | token-aware windowed LED + extractive fallback; ROUGE |
| `comparison/` | evidence extraction per dimension, pairwise comparison, multi-paper insights |
| `ingestion/` | upload validation, duplicate detection, background jobs, (re)indexing |
| `training/` | BGE-M3 data prep / fine-tune / baseline-vs-finetuned comparison; retrieval metrics; LED checkpoint eval |

## Data contract (unchanged core, extended)

`Paper → pages[{paper_id,page_number,extraction_method,raw_text,cleaned_text}] → sections[{section_name,heading,page_start,page_end,text,page_spans,subsections}] → chunks[{chunk_id,paper_id,section_name,page_start,page_end,text,…}]`, plus `title`, `analysis{keywords,entities,backends,warnings}`, `indexing`, `content_sha256`. Chunk ids: `{paper_id}_{SECTION}_{NNN}`, deterministic and unique even with repeated section names.
