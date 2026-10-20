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


def test_hybrid_falls_back_to_lexical_on_vector_dimension_mismatch(indexed, monkeypatch):
    from errors import VectorStoreUnavailable
    from vector_store import get_vector_store

    store = get_vector_store()

    def boom(*_a, **_k):
        raise VectorStoreUnavailable(
            "Redis index 'paper_chunks' was built with 1024-d vectors but the current embedder produces 384-d. "
            'Rebuild with POST /api/reindex {"reset": true} after the embedding model is stable.'
        )

    monkeypatch.setattr(store, "search", boom)
    out = search_chunks("BM25 negatives", mode="hybrid", include_low_confidence=True)
    assert out["results"] and any("Dense retrieval skipped" in w for w in out["warnings"])
    with pytest.raises(VectorStoreUnavailable, match="1024-d"):
        search_chunks("BM25 negatives", mode="dense")


class FakeLLM:
    configured, backend = True, "fake"

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.messages, self.max_tokens = reply, error, None, None
        self.timeout_seconds = None

    def info(self):
        return {"model": "fake"}

    def chat(self, messages, **kw):
        self.messages = messages
        self.max_tokens = kw.get("max_tokens")
        if self.error:
            raise self.error
        return self.reply

    def chat_with_info(self, messages, **kw):
        self.timeout_seconds = kw.get("timeout_seconds")
        return self.chat(messages, **kw), {"backend": self.backend, "model": "fake", "fallback_used": False}


def test_rag_answers_with_citations_and_evidence_metadata(indexed, monkeypatch):
    fake = FakeLLM("The model was trained on PubMedQA [1].")
    monkeypatch.setattr(chain, "llm", fake)
    out = answer_question("Which dataset was used for training?", top_k=4)
    assert out["status"] == "answered" and out["grounded"] is True and out["citations_used"] == [1]
    assert fake.timeout_seconds == min(float(chain.settings.llm_qa_timeout_seconds), 5.0)
    ev = out["evidence"][0]
    assert ev["ref"] == 1 and ev["paper_id"] and ev["section_name"] and ev["page_start"] and ev["text"]
    assert fake.max_tokens == min(int(chain.settings.llm_qa_max_tokens), 100)
    prompt = fake.messages[1]["content"]
    assert "[1] (paper:" in prompt and "Question: Which dataset" in prompt and "ONLY" in fake.messages[0]["content"]


def test_rag_uses_gemini_chat_timeout(indexed, monkeypatch):
    fake = FakeLLM("The model was trained on PubMedQA [1].")
    monkeypatch.setattr(chain.settings, "gemini_api_key", "gemini-test-key")
    monkeypatch.setattr(chain.settings, "gemini_timeout_seconds", 24.0)
    monkeypatch.setattr(chain.settings, "gemini_qa_max_tokens", 350)
    monkeypatch.setattr(chain, "get_chat_llm", lambda default_provider: fake)

    out = answer_question("Which dataset was used for training?")

    assert out["status"] == "answered"
    assert fake.timeout_seconds == 24.0
    assert fake.max_tokens == 350


def test_rag_uses_pre_retrieved_chunks_without_repeating_search(indexed, monkeypatch):
    fake = FakeLLM("The model was trained on PubMedQA [1].")
    monkeypatch.setattr(chain, "llm", fake)
    monkeypatch.setattr(chain, "search_chunks", lambda *args, **kwargs: pytest.fail("retrieval should not run twice"))
    out = answer_question(
        "Which dataset was used for training?",
        retrieved_chunks=[{
            "paper_id": "P001", "chunk_id": "P001_METHODOLOGY_001", "title": "Paper A",
            "section_name": "METHODOLOGY", "page_start": 1, "page_end": 1,
            "text": "The model was trained on PubMedQA.", "score": 0.02,
            "dense_score": 0.8, "lexical_coverage": 0.7, "supported": True,
        }],
        retrieval_metadata={"embedding_backend": "bge-m3", "vector_store": "memory", "warnings": []},
    )
    assert out["status"] == "answered" and out["retrieval"]["embedding_backend"] == "bge-m3"
    assert out["evidence"][0]["text"] == "The model was trained on PubMedQA."


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


def test_rag_without_llm_returns_extractive_cited_answer(indexed):
    out = answer_question("Which dataset was used for training?")
    assert out["status"] == "answered" and out["answer"] and out["evidence"]
    assert out["generation"]["backend"] == "extractive" and out["grounded"] is True
    assert any("No language model" in w for w in out["warnings"])


def test_rag_llm_failure_degrades_to_extractive(indexed, monkeypatch):
    monkeypatch.setattr(chain, "llm", FakeLLM(error=LLMUnavailable("The language model timed out.")))
    out = answer_question("Which dataset was used for training?")
    assert out["status"] == "answered" and out["answer"] and out["evidence"]
    assert out["generation"]["backend"] == "extractive" and out["grounded"] is True
    assert any("timed out" in w for w in out["warnings"])


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
