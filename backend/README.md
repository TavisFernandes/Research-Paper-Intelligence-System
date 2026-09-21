# Research Paper Intelligence Backend

The backend ingests PDFs, preserves paper → page → section → chunk provenance, derives scientific entities and keywords, indexes chunks for semantic retrieval, and exposes grounded Q&A, summaries, comparisons, and collection insights.

Heavy models and infrastructure are optional. By default the application uses a deterministic local embedding and extractive summarization fallback, so it starts without Redis, a Hugging Face download, or an LLM key. Configure Redis, BGE-M3, LED, and an OpenAI-compatible Qwen endpoint in `.env` to enable production components.

## Setup

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m spacy download en_core_web_sm
```

EasyOCR is used only when native text extraction is insufficient. First OCR use downloads its recognition weights.

## Run

```powershell
uvicorn main:app --reload --port 8000
```

Endpoints:

- `GET /api/health`, `GET /api/papers`, `POST /api/papers/upload`, `GET|DELETE /api/papers/{paper_id}`
- `POST /api/search`, `POST /api/qa`, `POST /api/summarize`
- `POST /api/compare`, `POST /api/insights`

The default temporary JSON storage directory is `backend/data`. Set `PAPER_STORAGE_DIR` to change it.

## Test

```powershell
py -m pytest -q
```

## Contract

`process_paper()` returns `paper_id`, `filename`, `total_pages`, `pages`, `sections`, `chunks`, `analysis`, and `indexing`. Every page preserves raw text; every section, chunk, answer citation, and comparison dimension retains source provenance.
