from pathlib import Path
from typing import Dict, Optional, Union
from uuid import uuid4

from .chunks import create_chunks
from .pdf import extract_pages
from .preprocess import clean_text
from .sections import detect_sections


def generate_paper_id(existing_ids: Optional[set[str]] = None) -> str:
    if existing_ids is None:
        return f"P-{uuid4().hex[:10].upper()}"
    index = 1
    while f"P{index:03d}" in existing_ids:
        index += 1
    return f"P{index:03d}"


def process_paper(path: Union[str, Path], paper_id: Optional[str] = None, chunk_size: int = 1200, overlap: int = 150) -> Dict[str, object]:
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
    return {
        "paper_id": resolved_id,
        "filename": source.name,
        "total_pages": len(pages),
        "pages": pages,
        "sections": sections,
        "chunks": chunks,
    }
