# Research Paper Intelligence System

Paperintel is a full-stack workspace for reading, searching, summarizing, questioning, and comparing research PDFs with source-linked evidence.

## Run locally

1. Copy `.env.example` to `.env` and optionally configure Redis and an OpenAI-compatible Qwen endpoint.
2. In `backend`, install `requirements.txt`, download `en_core_web_sm`, then run `uvicorn main:app --reload --port 8000`.
3. In `frontend`, run `pnpm install` then `pnpm --filter @workspace/research-paper-intelligence dev`.

The frontend proxies `/api` in development; otherwise set `VITE_API_BASE_URL=http://localhost:8000`.

## Architecture

`PDF → PyMuPDF text / EasyOCR fallback → spaCy preprocessing → sections → sentence-aware chunks → NER + keywords → BGE-M3 embeddings → Redis or local vector retrieval → RAG / summaries / comparisons`

## Evaluation and training

`backend/training/bge_m3/evaluate.py` reports Recall@K, MRR@10, and nDCG@K. `backend/training/bge_m3/finetune.py` accepts JSONL `{query, positive}` pairs (including PubMedQA-derived pairs). `backend/summarization/led/evaluate.py` reports ROUGE-1/2/L when references are available.
