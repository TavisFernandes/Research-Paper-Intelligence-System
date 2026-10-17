import pytest

import rag.chain as chain
from errors import InvalidInputError, LLMUnavailable
from ingestion.indexing import index_paper
from rag import INSUFFICIENT, answer_question
from retrieval import BM25Index, search_chunks
from training.bge_m3.evaluate import evaluate_rankings


@pytest.fixture
def indexed(paper_a, paper_b):
    index_paper(paper_a)
    index_paper(paper_b)
    return paper_a, paper_b


def test_bm25_ranks_term_matches_first():
    idx = BM25Index([{"chunk_id": "a", "text": "hard negatives mined with BM25"}, {"chunk_id": "b", "text": "image classification network"}])
    assert idx.search("BM25 negatives")[0]["chunk_id"] == "a" and idx.search("zzzz") == []


@pytest.mark.parametrize("mode", ["dense", "lexical", "hybrid"])
def test_modes_return_provenance(indexed, mode):
    out = search_chunks("hard negatives mined using BM25", top_k=3, mode=mode, include_low_confidence=True)
    top = out["results"][0]
    assert top["chunk_id"].startswith("P001_METHODOLOGY") and top["paper_id"] == "P001"
    assert {"title", "page_start", "page_end", "section_name", "chunk_id", "score", "rank"} <= top.keys()
    assert top["title"] == "Contrastive Retrieval for Scientific Papers"


def test_irrelevant_query_is_not_returned_as_evidence(indexed):
    out = search_chunks("quantum chromodynamics lattice gauge", top_k=5)
    assert out["results"] == [] and out["candidates"] >= 0
    weak = search_chunks("quantum chromodynamics lattice gauge", top_k=5, include_low_confidence=True)
    assert all(r["supported"] is False for r in weak["results"])


def test_paper_and_section_filters(indexed):
    out = search_chunks("CIFAR-10 accuracy", top_k=5, paper_ids=["P001"], include_low_confidence=True)
    assert all(r["paper_id"] == "P001" for r in out["results"])
    out = search_chunks("dataset", top_k=5, section_names=["RESULTS"], include_low_confidence=True)
    assert all(r["section_name"] == "RESULTS" for r in out["results"])


def test_empty_index_and_validation(paper_a):
    assert search_chunks("anything", top_k=3)["results"] == []
    with pytest.raises(InvalidInputError):
        search_chunks("   ")
    with pytest.raises(InvalidInputError):
        search_chunks("x", mode="bogus")


def test_warns_when_embeddings_are_not_semantic(indexed):
    assert any("non-semantic" in w for w in search_chunks("BM25 negatives", mode="hybrid")["warnings"])


class FakeLLM:
    configured, backend = True, "fake"

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.messages = reply, error, None

    def chat(self, messages, **kw):
        self.messages = messages
        if self.error:
            raise self.error
        return self.reply


def test_rag_answers_with_citations_and_evidence_metadata(indexed, monkeypatch):
    fake = FakeLLM("The model was trained on PubMedQA [1].")
    monkeypatch.setattr(chain, "llm", fake)
    out = answer_question("Which dataset was used for training?", top_k=4)
    assert out["status"] == "answered" and out["grounded"] is True and out["citations_used"] == [1]
    ev = out["evidence"][0]
    assert ev["ref"] == 1 and ev["paper_id"] and ev["section_name"] and ev["page_start"] and ev["text"]
    prompt = fake.messages[1]["content"]
    assert "[1] (paper:" in prompt and "Question: Which dataset" in prompt and "ONLY" in fake.messages[0]["content"]


def test_rag_flags_hallucinated_citations_and_missing_citations(indexed, monkeypatch):
    monkeypatch.setattr(chain, "llm", FakeLLM("It uses PubMedQA [9]."))
    out = answer_question("Which dataset was used for training?")
    assert any("non-existent" in w for w in out["warnings"]) and out["grounded"] is False
    monkeypatch.setattr(chain, "llm", FakeLLM("It uses PubMedQA."))
    assert any("no citations" in w for w in answer_question("Which dataset was used for training?")["warnings"])


def test_rag_model_refusal_is_reported_as_insufficient(indexed, monkeypatch):
    monkeypatch.setattr(chain, "llm", FakeLLM(INSUFFICIENT + " The papers do not say."))
    assert answer_question("Which dataset was used for training?")["status"] == "insufficient_evidence"


def test_rag_with_no_relevant_evidence_never_calls_llm(indexed, monkeypatch):
    fake = FakeLLM("should not be used")
    monkeypatch.setattr(chain, "llm", fake)
    out = answer_question("quantum chromodynamics lattice gauge")
    assert out["status"] == "insufficient_evidence" and out["evidence"] == [] and fake.messages is None
    assert "insufficient" in out["answer"].lower()


def test_rag_without_llm_returns_evidence_only(indexed):
    out = answer_question("Which dataset was used for training?")
    assert out["status"] == "evidence_only" and out["answer"] is None and out["evidence"] and "No language model" in out["message"]


def test_rag_llm_failure_degrades_gracefully(indexed, monkeypatch):
    monkeypatch.setattr(chain, "llm", FakeLLM(error=LLMUnavailable("The language model timed out.")))
    out = answer_question("Which dataset was used for training?")
    assert out["status"] == "llm_unavailable" and out["answer"] is None and out["evidence"] and "timed out" in out["message"]


def test_retrieval_metrics_known_values():
    m = evaluate_rankings([["a", "b", "c"], ["x", "y", "z"]], [{"b"}, {"q"}])
    assert m["mrr@10"] == 0.25 and m["recall@5"] == 0.5 and m["hit@5"] == 0.5
    assert round(m["ndcg@10"], 4) == round(0.5 * (1 / 1.5849625), 4)
    with pytest.raises(ValueError):
        evaluate_rankings([["a"]], [set()])
    with pytest.raises(ValueError):
        evaluate_rankings([["a"]], [])
    full = evaluate_rankings([["a", "b"]], [{"a", "b"}])
    assert full["recall@5"] == 1.0 and full["ndcg@10"] == 1.0
