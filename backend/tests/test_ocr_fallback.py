from pathlib import Path

from pdf_processing import pdf


def test_ocr_fallback_is_used_only_for_unusable_text(monkeypatch, tmp_path: Path):
    class FakePage:
        def extract_text(self):
            return ""

    class FakeReader:
        def __init__(self, path):
            self.pages = [FakePage()]

    monkeypatch.setattr("pypdf.PdfReader", FakeReader)
    monkeypatch.setattr(pdf, "_ocr_page", lambda path, page_number, dpi: ("scanned content", "ocr"))
    result = pdf.extract_pages(tmp_path / "scan.pdf")
    assert result == [{"page_number": 1, "extraction_method": "ocr", "raw_text": "scanned content"}]
