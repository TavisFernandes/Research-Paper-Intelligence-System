"""Grounded retrieval-augmented answering with citations."""
from embeddings import embedder
from llm import llm
from vector_store import vector_store


def answer_question(query: str, paper_ids: list[str] | None = None, section_name: str | None = None,
                    limit: int = 6) -> dict[str, object]:
    hits = vector_store.search(embedder.encode(query), limit=limit, paper_ids=paper_ids, section_name=section_name)
    citations = [{key: hit[key] for key in ("paper_id", "chunk_id", "section_name", "page_start", "page_end", "text", "score")}
                 for hit in hits]
    context = "\n\n".join(f"[{index + 1}] {hit['text']}" for index, hit in enumerate(hits))
    generated = llm.generate(query, context)
    if not generated:
        if not hits:
            generated = "I could not find supporting text in the selected papers."
        else:
            generated = "Based on the retrieved passages: " + " ".join(hit["text"] for hit in hits[:2])
    return {"answer": generated, "citations": citations, "retrieved_count": len(hits), "backend": llm.backend}
