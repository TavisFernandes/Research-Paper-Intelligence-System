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
