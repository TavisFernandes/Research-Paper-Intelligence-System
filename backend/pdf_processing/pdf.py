<<<<<<< HEAD
"""PDF text extraction: PyMuPDF for digital pages, EasyOCR only for image-based pages."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from config import settings
from errors import PdfIngestionError

logger = logging.getLogger(__name__)

# extraction_method values stored on every page
METHOD_TEXT = "text"
METHOD_OCR = "ocr"
METHOD_EMPTY = "empty"  # no text layer and no images: a genuinely blank page
METHOD_OCR_UNAVAILABLE = "ocr_unavailable"
METHOD_OCR_FAILED = "ocr_failed"


@dataclass
class ExtractedDocument:
    pages: List[Dict[str, object]]
    metadata: Dict[str, Any] = field(default_factory=dict)


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def _open_document(source: Path):
    """Open a PDF with PyMuPDF, translating failures into PdfIngestionError."""
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - dependency error
        raise PdfIngestionError("PyMuPDF is not installed on the server.") from exc
    if not source.exists():
        raise PdfIngestionError("The PDF file was not found.")
    if source.stat().st_size == 0:
        raise PdfIngestionError("The uploaded file is empty.")
    try:
        document = fitz.open(source)
    except Exception as exc:
        raise PdfIngestionError("The file is not a valid or readable PDF.") from exc
    if not document.is_pdf:
        document.close()
        raise PdfIngestionError("Unsupported file type: only PDF documents are accepted.")
    if document.needs_pass:
        # An empty user password is valid for some "encrypted" files.
        if not document.authenticate(""):
            document.close()
            raise PdfIngestionError("The PDF is password-protected and cannot be read.")
    if document.page_count == 0:
        document.close()
        raise PdfIngestionError("The PDF contains no pages.")
    return document


@lru_cache(maxsize=2)
def _ocr_reader(languages: str):
    """Load the EasyOCR reader once per process (model loading is slow)."""
    import easyocr

    use_gpu = False
    try:
        import torch

        use_gpu = bool(torch.cuda.is_available())
    except ImportError:
        pass
    return easyocr.Reader([lang.strip() for lang in languages.split(",") if lang.strip()], gpu=use_gpu, verbose=False)


def ocr_available() -> bool:
    try:
        import easyocr  # noqa: F401

        return True
    except ImportError:
        return False


def _ocr_page(page: Any, dpi: int) -> tuple[str, str]:
    """OCR a PyMuPDF page. Returns (text, extraction_method)."""
    if not settings.ocr_enabled or not ocr_available():
        return "", METHOD_OCR_UNAVAILABLE
    try:
        import numpy as np

        pixmap = page.get_pixmap(dpi=dpi, alpha=False)
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
        reader = _ocr_reader(settings.ocr_languages)
        lines = reader.readtext(image, detail=0, paragraph=True)
        return "\n".join(str(line) for line in lines), METHOD_OCR
    except Exception:
        logger.exception("OCR failed for page %s", getattr(page, "number", "?"))
        return "", METHOD_OCR_FAILED


def guess_title(document: Any) -> Optional[str]:
    """Guess the paper title as the largest-font text on page 1 (None when unreliable)."""
    try:
        blocks = document.load_page(0).get_text("dict").get("blocks", [])
        spans = [(span["size"], span["text"].strip(), line["bbox"][1])
                 for block in blocks if block.get("type") == 0 for line in block["lines"] for span in line["spans"] if span["text"].strip()]
        if not spans:
            return None
        biggest = max(size for size, _, _ in spans)
        lines = [(y, text) for size, text, y in spans if abs(size - biggest) < 0.6]
        lines.sort()
        title = re.sub(r"\s+", " ", " ".join(text for _, text in lines[:4])).strip()
        words = title.split()
        return title if 3 <= len(words) <= 40 and not re.search(r"^(arxiv|abstract|preprint)", title, re.I) else None
    except Exception:
        return None


def extract_document(path: Union[str, Path], minimum_words: Optional[int] = None, dpi: Optional[int] = None) -> ExtractedDocument:
    """Extract every page. Native text is preferred; OCR runs only for image-based pages.

    A page is OCR'd when it has fewer than ``minimum_words`` words *and* carries
    images (or has no text at all but is not provably blank).
    """
    minimum = settings.ocr_min_words if minimum_words is None else minimum_words
    resolution = settings.ocr_dpi if dpi is None else dpi
    document = _open_document(Path(path))
    try:
        metadata = {k: v for k, v in (document.metadata or {}).items() if v}
        metadata["title_guess"] = guess_title(document)
        pages: List[Dict[str, object]] = []
        for index in range(document.page_count):
            page = document.load_page(index)
            try:
                text = page.get_text("text") or ""
            except Exception:
                logger.exception("Text extraction failed on page %s", index + 1)
                text = ""
            method = METHOD_TEXT
            if _word_count(text) < minimum:
                has_images = bool(page.get_images(full=False))
                if has_images or (_word_count(text) == 0 and bool(page.get_drawings())):
                    ocr_text, ocr_method = _ocr_page(page, resolution)
                    if ocr_method == METHOD_OCR and _word_count(ocr_text) >= _word_count(text):
                        text, method = ocr_text, METHOD_OCR
                    elif ocr_method != METHOD_OCR:
                        method = ocr_method
                elif _word_count(text) == 0:
                    method = METHOD_EMPTY
            pages.append({"page_number": index + 1, "extraction_method": method, "raw_text": text})
        return ExtractedDocument(pages=pages, metadata=metadata)
    finally:
        document.close()


def extract_pages(path: Union[str, Path], minimum_words: Optional[int] = None, dpi: Optional[int] = None) -> List[Dict[str, object]]:
    """Backward-compatible wrapper returning only the page list."""
    return extract_document(path, minimum_words, dpi).pages
=======
from pathlib import Path
from typing import Dict, List, Union
import re


def _usable(text: str, minimum_words: int) -> bool:
    return len(re.findall(r"\w+", text)) >= minimum_words


def extract_pages(path: Union[str, Path], minimum_words: int = 3, dpi: int = 200) -> List[Dict[str, object]]:
    """Extract each page with text first and OCR only when text is insufficient."""
    source = Path(path)
    try:
        import fitz
        document = fitz.open(source)
        native_pages = [page.get_text("text") or "" for page in document]
        document.close()
    except Exception:
        try:
            from pypdf import PdfReader
            native_pages = [(page.extract_text() or "") for page in PdfReader(str(source)).pages]
        except ImportError as exc:
            raise RuntimeError("Install PyMuPDF or pypdf before extracting PDFs") from exc
    pages: List[Dict[str, object]] = []
    for number, text in enumerate(native_pages, start=1):
        method = "text"
        if not _usable(text, minimum_words):
            text, method = _ocr_page(source, number, dpi)
        pages.append({"page_number": number, "extraction_method": method, "raw_text": text})
    return pages


def _ocr_page(path: Path, page_number: int, dpi: int) -> tuple[str, str]:
    try:
        import fitz
        import easyocr
        from PIL import Image
    except ImportError:
        return "", "ocr_unavailable"
    try:
        document = fitz.open(path)
        page = document.load_page(page_number - 1)
        pixmap = page.get_pixmap(dpi=dpi, alpha=False)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        text = " ".join(reader.readtext(image, detail=0, paragraph=True))
        document.close()
        return text, "ocr"
    except Exception:
        return "", "ocr_failed"
>>>>>>> origin/main
