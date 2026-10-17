import pytest

from errors import PdfIngestionError
from pdf_processing import pdf as pdf_module
from pdf_processing.pdf import extract_document, extract_pages
from pdf_processing.pipeline import process_paper
from pdf_processing.preprocess import (clean_text, lemmatize_tokens, remove_repeated_lines, segment_sentences, tokenize_text)
from tests.helpers import make_blank_pdf, make_encrypted_pdf, make_pdf, make_scanned_pdf


def test_digital_pdf_extraction_preserves_pages_and_method(tmp_path):
    pages = extract_pages(make_pdf(tmp_path / "p.pdf"))
    assert [p["page_number"] for p in pages] == [1, 2]
    assert all(p["extraction_method"] == "text" for p in pages)
    assert "Abstract" in pages[0]["raw_text"] and "Limitations" in pages[1]["raw_text"]


def test_title_guess_uses_largest_font(tmp_path):
    doc = extract_document(make_pdf(tmp_path / "p.pdf"))
    assert doc.metadata["title_guess"] == "Contrastive Retrieval for Scientific Papers"


def test_scanned_page_without_ocr_is_flagged_not_silently_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_module, "ocr_available", lambda: False)
    pages = extract_pages(make_scanned_pdf(tmp_path / "s.pdf"))
    assert pages[0]["extraction_method"] == "ocr_unavailable"


def test_scanned_page_uses_ocr_when_available(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_module, "_ocr_page", lambda page, dpi: ("scanned words recovered by ocr engine today", "ocr"))
    pages = extract_pages(make_scanned_pdf(tmp_path / "s.pdf"))
    assert pages[0]["extraction_method"] == "ocr" and "recovered" in pages[0]["raw_text"]


def test_ocr_not_run_on_text_pages(tmp_path, monkeypatch):
    def boom(page, dpi):
        raise AssertionError("OCR must not run for digital pages")

    monkeypatch.setattr(pdf_module, "_ocr_page", boom)
    extract_pages(make_pdf(tmp_path / "p.pdf"))


def test_blank_page_is_marked_empty_and_rejected_by_pipeline(tmp_path):
    path = make_blank_pdf(tmp_path / "blank.pdf")
    assert extract_pages(path)[0]["extraction_method"] == "empty"
    with pytest.raises(PdfIngestionError, match="No extractable text"):
        process_paper(path, "P001")


@pytest.mark.parametrize("content", [b"", b"not a pdf at all", b"%PDF-1.4 truncated garbage"])
def test_corrupt_or_empty_pdfs_raise_clean_error(tmp_path, content):
    path = tmp_path / "bad.pdf"
    path.write_bytes(content)
    with pytest.raises(PdfIngestionError):
        extract_pages(path)


def test_encrypted_pdf_is_rejected_with_clear_message(tmp_path):
    with pytest.raises(PdfIngestionError, match="password"):
        extract_pages(make_encrypted_pdf(tmp_path / "enc.pdf"))


def test_missing_file(tmp_path):
    with pytest.raises(PdfIngestionError):
        extract_pages(tmp_path / "nope.pdf")


def test_clean_text_preserves_science():
    text = "Accuracy was 95.1% (p<0.05) [12].\nclassi-\nfication of state-of-the-art  models\ufb01"
    out = clean_text(text)
    assert "95.1%" in out and "(p<0.05)" in out and "[12]" in out
    assert "classification" in out and "state-of-the-art" in out and out.endswith("modelsfi")
    assert clean_text("hello\n  world") == "hello\nworld"


def test_sentence_segmentation_handles_abbreviations():
    sents = segment_sentences("Smith et al. reported 0.95 accuracy (see Fig. 2). The next sentence follows. Third one!")
    assert len(sents) == 3 and sents[0].endswith("Fig. 2).")


def test_tokenization_keeps_scientific_tokens():
    assert tokenize_text("CIFAR-10 reached 95.1 on F1-score") == ["CIFAR-10", "reached", "95.1", "on", "F1-score"]


def test_lemmatization_is_aligned_and_sensible():
    lemmas = lemmatize_tokens(["models", "studies", "running"])
    assert len(lemmas) == 3 and lemmas[0] == "model" and lemmas[1] == "study" and lemmas[2] in {"run", "running"}
    assert lemmatize_tokens([]) == []


def test_repeated_headers_removed_from_cleaned_text_only():
    bodies = ["alpha findings", "beta methods", "gamma results", "delta limits", "epsilon future"]
    pages = [f"Journal of X 2020\n{body}\nsome more text here\nand more text\nfinal line text\n{i}" for i, body in enumerate(bodies)]
    cleaned = remove_repeated_lines(pages)
    assert all("Journal of X" not in p for p in cleaned) and "gamma results" in cleaned[2]
    assert "Journal of X" in pages[0]  # input (raw) untouched


def test_full_pipeline_contract(tmp_path):
    paper = process_paper(make_pdf(tmp_path / "p.pdf"), "P001", chunk_size=300, overlap=50, filename="p.pdf")
    assert {"paper_id", "filename", "total_pages", "pages", "sections", "chunks", "analysis"} <= paper.keys()
    assert paper["pages"][0]["raw_text"] and paper["pages"][0]["cleaned_text"]
    names = [s["section_name"] for s in paper["sections"]]
    assert names[:3] == ["UNKNOWN", "ABSTRACT", "INTRODUCTION"] and "FUTURE_WORK" in names
    assert paper["title"] == "Contrastive Retrieval for Scientific Papers"
    assert paper["indexing"]["indexed"] is True
    labels = {(e["label"], e["text"]) for e in paper["analysis"]["entities"]}
    assert ("DATASET", "PubMedQA") in labels and ("METRIC", "Recall@10") in labels and ("MODEL", "BGE-M3") in labels
