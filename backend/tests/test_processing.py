from pathlib import Path

import fitz

from pdf_processing.chunks import create_chunks
from pdf_processing.pdf import extract_pages
from pdf_processing.pipeline import process_paper
from pdf_processing.preprocess import clean_text, lemmatize_tokens, segment_sentences, tokenize_text
from pdf_processing.sections import detect_sections


def make_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "ABSTRACT\nThis study tests models.\n\nINTRODUCTION\nResearch papers need structure.")
    document.save(path)
    document.close()


def test_text_extraction_and_complete_pipeline(tmp_path: Path):
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)
    pages = extract_pages(pdf_path)
    assert pages[0]["extraction_method"] == "text"
    paper = process_paper(pdf_path, paper_id="P001", chunk_size=40, overlap=5)
    assert paper["paper_id"] == "P001"
    assert paper["pages"][0]["raw_text"]
    assert paper["pages"][0]["cleaned_text"]
    assert paper["sections"][0]["section_name"] == "ABSTRACT"
    assert paper["chunks"][0]["chunk_id"].startswith("P001_ABSTRACT_")


def test_preprocessing():
    assert clean_text("hello\n  world") == "hello\nworld"
    assert segment_sentences("One sentence. Two sentences!") == ["One sentence.", "Two sentences!"]
    assert tokenize_text("Models' results") == ["Models'", "results"]
    assert lemmatize_tokens(["models", "studies", "running"]) == ["model", "study", "runn"]


def test_section_detection_and_chunk_validation():
    pages = [{"paper_id": "P1", "page_number": 1, "cleaned_text": "METHODS\nA method."}]
    sections = detect_sections(pages, "P1")
    assert sections[0]["section_name"] == "METHODOLOGY"
    assert len(create_chunks(sections, chunk_size=5, overlap=1)) > 1
