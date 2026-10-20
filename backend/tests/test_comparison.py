import re

import pytest

from comparison import DIMENSIONS, compare_papers, extract_dimension, extract_reported_results, research_insights
from comparison.service import NOT_REPORTED, _recurring_themes_terms
from errors import InvalidInputError


def test_dimension_extraction_is_verbatim_with_provenance(paper_a):
    ds = extract_dimension(paper_a, "datasets")
    assert ds["status"] == "found" and "PubMedQA" in ds["entities"]
    for ev in ds["evidence"]:
        assert ev["text"].rstrip("…") in " ".join(s["text"].replace("\n", " ") for s in paper_a["sections"])
        assert ev["page_start"] >= 1 and ev["section_name"]
    assert extract_dimension(paper_a, "future_work")["evidence"][0]["section_name"] == "FUTURE_WORK"
    lim = extract_dimension(paper_a, "limitations")
    assert lim["evidence"][0]["section_name"] == "LIMITATIONS" and "biomedical" in lim["evidence"][0]["text"]


def test_missing_dimension_is_not_reported_not_invented(paper_b):
    out = extract_dimension(paper_b, "limitations")
    assert out["status"] == "not_reported" and out["evidence"] == [] and out["entities"] == []


def test_reported_results_are_copied_not_computed(paper_a, paper_b):
    pairs = extract_reported_results(paper_a)
    values = {p["value"] for p in pairs}
    assert "0.91" in values
    for paper in (paper_a, paper_b):
        source = " ".join(s["text"] for s in paper["sections"])
        assert all(p["value"] in source for p in extract_reported_results(paper))


def test_pairwise_comparison_structure(paper_a, paper_b):
    out = compare_papers(paper_a, paper_b)
    assert [r["dimension"] for r in out["table"]] == [d["label"] for d in DIMENSIONS]
    assert len(out["table"]) == 10
    limitations = next(r for r in out["table"] if r["dimension"] == "Limitations")
    assert limitations["right"]["text"] == NOT_REPORTED and limitations["left"]["sources"]
    datasets = next(d for d in out["dimensions"] if d["key"] == "datasets")
    assert "PubMedQA" in datasets["entity_overlap"]["only_left"] and "CIFAR-10" in datasets["entity_overlap"]["only_right"]
    assert datasets["entity_overlap"]["type"] == "inferred"
    assert -1 <= out["overall_similarity"] <= 1 and out["similarity_basis"]
    assert out["narrative"] is None and "reported" in out["provenance"] and "inferred" in out
    assert any("not reported" in d for d in out["inferred"]["differences"])


def test_compare_same_paper_rejected(paper_a):
    with pytest.raises(InvalidInputError):
        compare_papers(paper_a, paper_a)


def test_narrative_without_llm_is_marked_unavailable(paper_a, paper_b):
    assert compare_papers(paper_a, paper_b, use_llm=True)["narrative"]["status"] == "unavailable"


def test_insights(paper_a, paper_b):
    out = research_insights([paper_a, paper_b])
    assert out["similarity_matrix"]["paper_ids"] == ["P001", "P002"] and out["similarity_matrix"]["values"][0][0] == pytest.approx(1.0, abs=1e-3)
    names = {d["name"]: d for d in out["common_datasets"]}
    assert names["PubMedQA"]["papers"] == ["P001"] and names["PubMedQA"]["common"] is False
    assert out["research_gaps"]["inferred"] and all(g["type"] == "inferred" for g in out["research_gaps"]["inferred"])
    assert out["research_gaps"]["reported_future_work"][0]["type"] == "reported"
    assert "no temporal trend" in out["recurring_themes"]["note"]
    metric_names = {m["metric"].lower() for m in out["performance_patterns"]["metrics"]}
    assert "accuracy" in metric_names
    numbers = {n for m in out["performance_patterns"]["metrics"] for r in m["reports"] for n in re.findall(r"\d+(?:\.\d+)?", r["value"])}
    text = " ".join(s["text"] for p in (paper_a, paper_b) for s in p["sections"])
    assert all(n in text for n in numbers)  # no number appears that is not in the papers


def test_insights_need_two_papers(paper_a):
    with pytest.raises(InvalidInputError):
        research_insights([paper_a])


def test_recurring_themes_use_cached_keywords_and_fallback(monkeypatch):
    papers = [
        {"paper_id": "P001", "analysis": {"keywords": [{"keyword": "shared"}, {"keyword": "two words"}]},
         "chunks": [{"text": "ignored cached paper content"}]},
        {"paper_id": "P002", "analysis": {"keywords": [{"keyword": "shared"}]}},
        {"paper_id": "P003", "chunks": [{"text": "fallback paper content"}]},
    ]
    monkeypatch.setattr("comparison.service.extract_keywords", lambda text, limit: [{"keyword": "shared"}, {"keyword": "fallback"}])

    assert _recurring_themes_terms(papers) == [
        {"term": "shared", "papers": ["P001", "P002", "P003"], "count": 3}
    ]
