<<<<<<< HEAD
"""Module-1 pipeline: PDF -> pages -> cleaning -> sections -> chunks -> analysis -> index."""
from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional, Union
from uuid import uuid4

from config import settings
from errors import PdfIngestionError
from nlp import extract_entities, extract_keywords, ner_status

from .chunks import create_chunks
from .pdf import ExtractedDocument, extract_document
from .preprocess import clean_text, lemmatize_tokens, nlp_status, remove_repeated_lines, segment_sentences, tokenize_text
from .sections import detect_sections

logger = logging.getLogger(__name__)
ProgressFn = Callable[[str, int], None]
MIN_TOTAL_WORDS = 20
=======
from pathlib import Path
from typing import Dict, Optional, Union
from uuid import uuid4

from .chunks import create_chunks
from .pdf import extract_pages
from .preprocess import clean_text
from .sections import detect_sections
from config import settings
from nlp import extract_entities, extract_keywords
from embeddings import embedder
from vector_store import vector_store
>>>>>>> origin/main


def generate_paper_id(existing_ids: Optional[set[str]] = None) -> str:
    if existing_ids is None:
        return f"P-{uuid4().hex[:10].upper()}"
    index = 1
    while f"P{index:03d}" in existing_ids:
        index += 1
    return f"P{index:03d}"


<<<<<<< HEAD
def _choose_title(extracted: ExtractedDocument, filename: str) -> tuple[Optional[str], Optional[str]]:
    meta = str(extracted.metadata.get("title") or "").strip()
    if 8 <= len(meta) <= 250 and not re.search(r"\.(pdf|docx?|tex|dvi)$|untitled|microsoft word", meta, re.I):
        return meta, "pdf_metadata"
    guess = extracted.metadata.get("title_guess")
    if guess:
        return str(guess), "first_page_largest_font"
    return None, None


def build_structure(extracted: ExtractedDocument, paper_id: str, chunk_size: int, overlap: int) -> Dict[str, object]:
    """Pure (model-free) part of the pipeline; useful for tests and offline use."""
    raw_pages = extracted.pages
    cleaned = remove_repeated_lines([clean_text(str(p["raw_text"])) for p in raw_pages])
    pages = [{
        "paper_id": paper_id, "page_number": p["page_number"], "extraction_method": p["extraction_method"],
        "raw_text": p["raw_text"], "cleaned_text": text,
    } for p, text in zip(raw_pages, cleaned)]
    sections = detect_sections(pages, paper_id)
    chunks = create_chunks(sections, chunk_size=chunk_size, overlap=overlap, include_references=settings.index_references)
    return {"pages": pages, "sections": sections, "chunks": chunks}


def process_paper(path: Union[str, Path], paper_id: Optional[str] = None, chunk_size: Optional[int] = None,
                  overlap: Optional[int] = None, filename: Optional[str] = None, content_sha256: Optional[str] = None,
                  progress: Optional[ProgressFn] = None, index: bool = True) -> Dict[str, object]:
    """Process one PDF end to end and return the stable paper data contract (plus analysis)."""
    note: ProgressFn = progress or (lambda stage, pct: None)
    source = Path(path)
    resolved_id = paper_id or generate_paper_id()
    chunk_size = chunk_size or settings.chunk_size
    overlap = settings.chunk_overlap if overlap is None else overlap

    note("extracting_text", 10)
    extracted = extract_document(source)
    total_words = sum(len(re.findall(r"\w+", str(p["raw_text"]))) for p in extracted.pages)
    if total_words < MIN_TOTAL_WORDS:
        methods = Counter(str(p["extraction_method"]) for p in extracted.pages)
        hint = " OCR is unavailable (pip install easyocr)." if methods.get("ocr_unavailable") else ""
        raise PdfIngestionError(f"No extractable text was found in this PDF.{hint}")

    note("preprocessing", 30)
    structure = build_structure(extracted, resolved_id, chunk_size, overlap)
    pages, sections, chunks = structure["pages"], structure["sections"], structure["chunks"]  # type: ignore[assignment]
    title, title_source = _choose_title(extracted, filename or source.name)
    shown_name = filename or source.name
    for chunk in chunks:  # type: ignore[union-attr]
        chunk["title"] = title or ""
        chunk["filename"] = shown_name

    note("section_detection", 45)
    note("analysis", 60)
    full_text = "\n".join(str(p["cleaned_text"]) for p in pages)  # type: ignore[union-attr]
    tokens = tokenize_text(full_text)
    lemmas = lemmatize_tokens(tokens)
    lemma_counts = Counter(l for l in lemmas if len(l) > 3 and l.isalpha())
    keywords = extract_keywords(full_text, documents=[str(c["text"]) for c in chunks])  # type: ignore[union-attr]
    entities = extract_entities(full_text)
    ocr_pages = sum(1 for p in pages if p["extraction_method"] == "ocr")  # type: ignore[union-attr]
    skipped = [p["page_number"] for p in pages if str(p["extraction_method"]) in {"ocr_unavailable", "ocr_failed"}]  # type: ignore[union-attr]
    warnings = []
    if skipped:
        warnings.append(f"OCR was needed but unavailable/failed on pages {skipped}; those pages have no text.")
    unknown_chars = sum(len(str(s["text"])) for s in sections if s["section_name"] == "UNKNOWN")  # type: ignore[union-attr]
    if sections and unknown_chars > 0.6 * sum(len(str(s["text"])) for s in sections):  # type: ignore[union-attr]
        warnings.append("Most text could not be assigned to a known section (no recognisable headings).")

    paper: Dict[str, object] = {
        "paper_id": resolved_id,
        "filename": shown_name,
        "title": title,
        "title_source": title_source,
        "total_pages": len(pages),  # type: ignore[arg-type]
        "pages": pages,
        "sections": sections,
        "chunks": chunks,
        "analysis": {
            "keywords": keywords,
            "entities": entities,
            "top_lemmas": [{"lemma": l, "count": c} for l, c in lemma_counts.most_common(20)],
            "backends": {"nlp": nlp_status()["backend"], **ner_status()},
            "warnings": warnings,
        },
        "preprocessing": {"sentence_count": len(segment_sentences(full_text)), "token_count": len(tokens), "unique_lemmas": len(set(lemmas))},
        "extraction": {"ocr_pages": ocr_pages, "pdf_metadata": {k: v for k, v in extracted.metadata.items() if k != "title_guess"}},
        "content_sha256": content_sha256,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "processed",
    }
    paper["indexing"] = {"chunk_count": len(chunks), "indexed": False, "embedding_backend": None, "vector_store": None}  # type: ignore[arg-type]
    if index and chunks:  # type: ignore[truthy-bool]
        from ingestion.indexing import index_paper

        note("embedding_and_indexing", 80)
        paper["indexing"] = index_paper(paper)
        paper["status"] = "indexed"
    note("done", 100)
    return paper
=======
def process_paper(path: Union[str, Path], paper_id: Optional[str] = None, chunk_size: int = settings.chunk_size, overlap: int = settings.chunk_overlap) -> Dict[str, object]:
    source = Path(path)
    resolved_id = paper_id or generate_paper_id()
    raw_pages = extract_pages(source)
    pages = []
    for page in raw_pages:
        pages.append({
            "paper_id": resolved_id,
            "page_number": page["page_number"],
            "extraction_method": page["extraction_method"],
            "raw_text": page["raw_text"],
            "cleaned_text": clean_text(str(page["raw_text"])),
        })
    sections = detect_sections(pages, resolved_id)
    chunks = create_chunks(sections, chunk_size=chunk_size, overlap=overlap)
    full_text = "\n".join(page["cleaned_text"] for page in pages)
    analysis = {"keywords": extract_keywords(full_text), "entities": extract_entities(full_text)}
    if chunks:
        vector_store.delete_paper(resolved_id)
        vector_store.upsert_chunks(chunks, embedder.encode([str(chunk["text"]) for chunk in chunks]))
    return {
        "paper_id": resolved_id,
        "filename": source.name,
        "total_pages": len(pages),
        "pages": pages,
        "sections": sections,
        "chunks": chunks,
        "analysis": analysis,
        "indexing": {"chunk_count": len(chunks), "embedding_backend": embedder.backend, "vector_store": vector_store.backend},
    }
>>>>>>> origin/main
