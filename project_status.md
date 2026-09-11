# Project Status

## Overall Status

Frontend: Existing / under development

Backend: Initial development stage

Current focus: PDF Processing & Document Understanding

### Frontend ↔ Backend Integration

Status: Implemented / In Progress

- Frontend PDF upload is connected to the FastAPI upload endpoint.
- Paper processing and retrieval are connected through a centralized frontend API service.
- The processed paper response is displayed dynamically from pages, sections, and chunks.
- Demo/static paper records and analysis outputs were removed from active application state.
- The frontend includes an NLP pipeline visualization for the implemented Module 1 stages.
- NLP analysis, embeddings, retrieval, summarization, Q&A, and comparison remain future modules.
- The frontend uses the Vite `/api` proxy by default; set `VITE_API_BASE_URL` when the backend runs elsewhere.

## Completed

- Project concept defined
- Main project features defined
- High-level workflow defined
- High-level architecture defined
- Frontend exists
- Backend Module 1 implementation created
- Project context files created

## Current Work

### Module 1 — PDF Processing & Document Understanding

Status: IN PROGRESS

Scope:

- PDF input
- Page-level text extraction
- OCR fallback
- Page metadata
- Text cleaning
- Sentence segmentation
- Tokenization
- Lemmatization
- Section identification
- Chunk creation
- Structured output

Implementation milestone:

- Core pipeline, API, tests, and module documentation are present.
- Additional real scanned-paper validation remains before this module is considered complete.

## Future Modules

### Module 2 — NLP Analysis & Information Extraction

Includes TF-IDF, NER, keyword analysis, and research information extraction.

Status: Not started

### Module 3 — Semantic Embeddings & Retrieval

Potential technologies: BGE-M3 and a vector database.

Status: Not started. Technology not finalized.

### Module 4 — Long-Document Summarization

Potential model: LED / Longformer Encoder-Decoder.

Evaluation: ROUGE-1, ROUGE-2, ROUGE-L.

Status: Not started. Model and evaluation setup not finalized.

### Module 5 — Question Answering / RAG

Status: Not started

### Module 6 — Pairwise Paper Comparison

Status: Not started

### Module 7 — Multi-Paper Research Insights

Status: Not started

## Experimental Technology Choices

### PyMuPDF and pypdf

Technology: PyMuPDF and pypdf
Purpose: Page rendering and normal PDF text extraction
Status: Experimental / Provisional
Alternatives: Other PDF parsers and renderers
Notes: pypdf is attempted first; PyMuPDF is used for OCR rendering when available.

### pytesseract

Technology: pytesseract with a local Tesseract installation
Purpose: OCR fallback for pages without usable extracted text
Status: Experimental / Provisional
Alternatives: Other OCR engines
Notes: OCR is optional and only attempted for pages below the usable-text threshold. Tesseract must be installed separately.

### FastAPI

Technology: FastAPI and Uvicorn
Purpose: Thin API wrapper for upload, process, and retrieval
Status: Experimental / Provisional
Alternatives: Existing project API server or another Python web framework
Notes: This backend is intentionally isolated from the existing frontend workspace.

## Known Constraints

- `/frontend` must not be modified while backend modules are independently developed.
- Raw extracted text must be preserved.
- Page numbers must be preserved.
- OCR should only be used where necessary.
- Data contracts should remain stable.
- Technology choices are still under evaluation.
- Rule-based lemmatization is a lightweight provisional fallback and is not a substitute for a trained linguistic model.
- OCR requires the Tesseract executable in addition to the Python package.

## Next Steps

1. Validate OCR using representative scanned research papers.
2. Tune section-heading and chunk-size rules against the team's sample papers.
3. Complete PDF extraction and preprocessing acceptance tests.
4. Finalize the Module 1 interface for downstream developers.
5. Begin Module 2 only after the Module 1 contract is accepted.

## Change Log

### Initial Backend Setup

- Created project context documentation.
- Created project status tracking.
- Started Module 1: PDF Processing & Document Understanding.

### Module 1 Core Implementation

- Added modular PDF extraction, optional OCR, preprocessing, section detection, chunking, storage, API endpoints, tests, and documentation.
