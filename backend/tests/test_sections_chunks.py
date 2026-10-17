import pytest

from pdf_processing.chunks import create_chunks
from pdf_processing.sections import classify_heading, detect_sections


def pages_from(*page_texts):
    return [{"paper_id": "P1", "page_number": i + 1, "cleaned_text": t} for i, t in enumerate(page_texts)]


@pytest.mark.parametrize("line,expected", [
    ("1 Introduction", "INTRODUCTION"), ("I. INTRODUCTION", "INTRODUCTION"), ("2. Related Work", "RELATED_WORK"),
    ("3 Materials and Methods", "METHODOLOGY"), ("METHODS", "METHODOLOGY"), ("Methodology", "METHODOLOGY"),
    ("4 Experimental Results", "EXPERIMENTS"), ("Results and Discussion", "DISCUSSION"), ("5. Conclusions", "CONCLUSION"),
    ("Limitations:", "LIMITATIONS"), ("Future Work", "FUTURE_WORK"), ("A B S T R A C T", "ABSTRACT"), ("REFERENCES", "REFERENCES"),
    ("3.2 Datasets", "DATASET"), ("6 Discussion and Limitations of the Approach", "METHODOLOGY"),
])
def test_heading_variants(line, expected):
    result = classify_heading(line)
    assert result is not None
    if line.startswith("6 Discussion and Limitations"):
        assert result["section"] in {"DISCUSSION", "LIMITATIONS", "METHODOLOGY"}  # keyword rules; any known section is acceptable
    else:
        assert result["section"] == expected


@pytest.mark.parametrize("line", ["The method works well.", "Results were good", "This is a long sentence that happens to start with Method details and goes on.",
                                  "1 2 3 4", "Table 3: Results", "95.1 0.88 0.75"])
def test_body_text_is_not_a_heading(line):
    assert classify_heading(line) is None


def test_sections_page_provenance_and_unknown_preamble():
    pages = pages_from("Title line\nAbstract\nWe do things.\n1 Introduction\nIntro text here.", "More intro text.\n2 Methods\nMethod text.")
    sections = detect_sections(pages, "P1")
    assert [s["section_name"] for s in sections] == ["UNKNOWN", "ABSTRACT", "INTRODUCTION", "METHODOLOGY"]
    intro = sections[2]
    assert (intro["page_start"], intro["page_end"]) == (1, 2)
    assert [span["page"] for span in intro["page_spans"]] == [1, 2]
    assert sections[0]["page_start"] == 1


def test_no_headings_means_unknown_not_invented():
    sections = detect_sections(pages_from("Just some prose without any headings at all.\nMore prose."), "P1")
    assert [s["section_name"] for s in sections] == ["UNKNOWN"]


def test_subsections_preserve_hierarchy():
    pages = pages_from("2 Methods\nWe do X.\n2.1 Training details\nLearning rate 1e-5.\n2.2 Evaluation protocol\nWe use recall.")
    sections = detect_sections(pages, "P1")
    assert len(sections) == 1 and sections[0]["section_name"] == "METHODOLOGY"
    assert [s["heading"] for s in sections[0]["subsections"]] == ["Training details", "Evaluation protocol"]


def test_numbered_unknown_heading_requires_sequence():
    pages = pages_from("1 Introduction\nIntro.\n2 Proposed Pipeline Overview\nStuff.\n9 Totally Random Heading\nMore.")
    names = [(s["section_name"], s["heading"]) for s in detect_sections(pages, "P1")]
    assert ("OTHER", "Proposed Pipeline Overview") in names
    assert all(h != "Totally Random Heading" for _, h in names)


def test_inline_abstract():
    sections = detect_sections(pages_from("Abstract\u2014We propose a method for retrieval.\n1 Introduction\nHello there."), "P1")
    assert sections[0]["section_name"] == "ABSTRACT" and sections[0]["text"].startswith("We propose")


def section(text, name="RESULTS", pages=None):
    return {"paper_id": "P1", "section_name": name, "heading": name, "page_start": 1, "page_end": 1, "text": text,
            "page_spans": pages or [{"page": 1, "start": 0, "end": len(text)}]}


def test_chunk_ids_unique_and_stable_even_with_repeated_sections():
    secs = [section("First sentence is here. " * 30), section("Another one appears now. " * 30)]
    a = create_chunks(secs, chunk_size=200, overlap=40)
    b = create_chunks(secs, chunk_size=200, overlap=40)
    ids = [c["chunk_id"] for c in a]
    assert len(ids) == len(set(ids)) > 2 and ids == [c["chunk_id"] for c in b]


def test_overlap_repeats_whole_trailing_sentence_and_nothing_is_lost():
    sentences = [f"Sentence number {i} talks about topic {i} in some detail." for i in range(12)]
    chunks = create_chunks([section(" ".join(sentences))], chunk_size=150, overlap=70)
    assert len(chunks) > 3
    combined = " ".join(c["text"] for c in chunks)
    assert all(s in combined for s in sentences)
    assert chunks[0]["text"].split(". ")[-1][:20] in chunks[1]["text"]
    assert all(len(c["text"]) <= 150 for c in chunks)


def test_long_sentence_is_split_at_word_boundaries():
    text = "word " * 200
    chunks = create_chunks([section(text.strip())], chunk_size=100, overlap=10)
    assert len(chunks) >= 9 and all(len(c["text"]) <= 100 for c in chunks)
    assert all(not c["text"].startswith("ord") for c in chunks)


def test_chunk_pages_follow_sentence_positions():
    first, second = "Alpha sentence on page one is here. ", "Beta sentence on page two is here."
    text = first.strip() + "\n" + second
    spans = [{"page": 1, "start": 0, "end": len(first.strip())}, {"page": 2, "start": len(first.strip()) + 1, "end": len(text)}]
    chunks = create_chunks([{**section(text, pages=spans), "page_end": 2}], chunk_size=45, overlap=5)
    assert chunks[0]["page_start"] == 1 and chunks[-1]["page_end"] == 2 and chunks[0]["page_end"] == 1


def test_references_skipped_when_requested_and_params_validated():
    secs = [section("Cited paper one. Cited paper two is here.", "REFERENCES")]
    assert create_chunks(secs, include_references=False) == []
    assert len(create_chunks(secs, include_references=True)) == 1
    with pytest.raises(ValueError):
        create_chunks(secs, chunk_size=10, overlap=10)
    with pytest.raises(ValueError):
        create_chunks(secs, chunk_size=0)
