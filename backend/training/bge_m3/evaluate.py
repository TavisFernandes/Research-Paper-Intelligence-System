"""Standard retrieval evaluation metrics with no framework dependency."""
import math


def evaluate_rankings(rankings: list[list[str]], relevant: list[set[str]], ks: tuple[int, ...] = (5, 10)) -> dict[str, float]:
    if len(rankings) != len(relevant):
        raise ValueError("rankings and relevant sets must have equal length")
    results: dict[str, float] = {}
    for k in ks:
        results[f"recall@{k}"] = sum(bool(set(items[:k]) & targets) for items, targets in zip(rankings, relevant)) / max(len(relevant), 1)
        results[f"ndcg@{k}"] = sum(_ndcg(items[:k], targets) for items, targets in zip(rankings, relevant)) / max(len(relevant), 1)
    results["mrr@10"] = sum(_reciprocal_rank(items[:10], targets) for items, targets in zip(rankings, relevant)) / max(len(relevant), 1)
    return {key: round(value, 5) for key, value in results.items()}


def _reciprocal_rank(items: list[str], targets: set[str]) -> float:
    return next((1 / (position + 1) for position, item in enumerate(items) if item in targets), 0.0)


def _ndcg(items: list[str], targets: set[str]) -> float:
    dcg = sum(1 / math.log2(position + 2) for position, item in enumerate(items) if item in targets)
    ideal = sum(1 / math.log2(position + 2) for position in range(min(len(targets), len(items))))
    return dcg / ideal if ideal else 0.0
