"""Evidence-preserving pairwise and collection-level paper comparison."""
from collections import Counter
from embeddings import embedder
from vector_store.redis_store import _cosine


_DIMENSIONS = ("ABSTRACT", "INTRODUCTION", "METHODOLOGY", "DATASET", "EXPERIMENTS", "RESULTS", "LIMITATIONS", "CONCLUSION")


def _section_text(paper: dict, name: str) -> str:
    return " ".join(section["text"] for section in paper.get("sections", []) if section["section_name"] == name)[:2500]


def compare_papers(left: dict, right: dict) -> dict[str, object]:
    dimensions = []
    for name in _DIMENSIONS:
        left_text, right_text = _section_text(left, name), _section_text(right, name)
        score = _cosine(embedder.encode(left_text), embedder.encode(right_text)) if left_text and right_text else None
        dimensions.append({"dimension": name, "left": left_text or "Not identified", "right": right_text or "Not identified", "similarity": round(score, 3) if score is not None else None})
    all_left = " ".join(chunk["text"] for chunk in left.get("chunks", []))
    all_right = " ".join(chunk["text"] for chunk in right.get("chunks", []))
    overall = _cosine(embedder.encode(all_left), embedder.encode(all_right)) if all_left and all_right else 0.0
    return {"left_paper_id": left["paper_id"], "right_paper_id": right["paper_id"], "overall_similarity": round(overall, 3), "dimensions": dimensions}


def research_insights(papers: list[dict]) -> dict[str, object]:
    keywords = Counter(item["keyword"] for paper in papers for item in paper.get("analysis", {}).get("keywords", []))
    entity_types = Counter(entity["label"] for paper in papers for entity in paper.get("analysis", {}).get("entities", []))
    pairs = [compare_papers(papers[a], papers[b]) for a in range(len(papers)) for b in range(a + 1, len(papers))]
    return {"paper_count": len(papers), "common_keywords": [key for key, _ in keywords.most_common(12)], "entity_type_counts": dict(entity_types), "pairwise": pairs}
