# PDF Processing Backend

Module 1 implements PDF Processing & Document Understanding only. It preserves page metadata and raw text, uses normal text extraction before optional OCR, and produces section-aware chunks.

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

OCR additionally requires the Tesseract executable to be installed and available on `PATH`. Without it, pages with no usable text are returned with `extraction_method: "ocr_unavailable"` rather than silently losing content.

## Run

```powershell
uvicorn pdf_processing.api:app --reload --port 8000
```

Endpoints:

- `POST /api/papers/upload` with multipart field `file`
- `POST /api/papers/process/{paper_id}` reprocesses the retained upload
- `GET /api/papers/{paper_id}`

The default temporary JSON storage directory is `backend/data`. Set `PAPER_STORAGE_DIR` to change it.

## Test

```powershell
python -m pytest -q
```

## Contract

`process_paper()` returns a dictionary with `paper_id`, `filename`, `total_pages`, `pages`, `sections`, and `chunks`. Every page preserves `raw_text` and `cleaned_text`; every section and chunk carries source page metadata.
