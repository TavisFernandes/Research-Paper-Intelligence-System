from comparison import compare_papers
from embeddings.bge_m3 import BgeM3Embedder
from nlp import extract_entities, extract_keywords
from summarization.led import summarize
from training.bge_m3.evaluate import evaluate_rankings
from vector_store.redis_store import RedisVectorStore


def test_local_retrieval_is_filterable():
    store = RedisVectorStore(url="redis://localhost:1")
    encoder = BgeM3Embedder(dimensions=32, force_hashing=True)
    chunks = [{"paper_id": "P1", "chunk_id": "P1_001", "section_name": "METHODS", "page_start": 1, "page_end": 1, "text": "Transformers use attention."}]
    store.upsert_chunks(chunks, encoder.encode([chunks[0]["text"]]))
    assert store.search(encoder.encode("attention"), paper_ids=["P1"])[0]["chunk_id"] == "P1_001"


def test_analysis_and_summary_have_usable_fallbacks():
    assert extract_keywords("transformer transformer attention")[0]["keyword"] == "transformer"
    assert any(entity["label"] == "MODEL" for entity in extract_entities("BERT improves accuracy"))
    assert summarize("First sentence. A longer second sentence with important details.")["summary"]


def test_comparison_and_evaluation():
    paper = {"paper_id": "P1", "sections": [{"section_name": "METHODOLOGY", "text": "attention model"}], "chunks": [{"text": "attention model"}]}
    other = {"paper_id": "P2", "sections": [{"section_name": "METHODOLOGY", "text": "attention model"}], "chunks": [{"text": "attention model"}]}
    assert compare_papers(paper, other)["overall_similarity"] > 0.9
    assert evaluate_rankings([["a", "b"]], [{"b"}])["mrr@10"] == 0.5
