<<<<<<< HEAD
"""Retrieval metrics (Recall@5/10, MRR@10, nDCG@10) with no framework dependency."""
from __future__ import annotations

import math
from typing import Dict, Sequence, Set


def _reciprocal_rank(items: Sequence[str], targets: Set[str]) -> float:
    return next((1 / (pos + 1) for pos, item in enumerate(items) if item in targets), 0.0)


def _ndcg(items: Sequence[str], targets: Set[str], k: int) -> float:
    dcg = sum(1 / math.log2(pos + 2) for pos, item in enumerate(items[:k]) if item in targets)
    ideal = sum(1 / math.log2(pos + 2) for pos in range(min(len(targets), k)))
    return dcg / ideal if ideal else 0.0


def evaluate_rankings(rankings: Sequence[Sequence[str]], relevant: Sequence[Set[str]], ks: Sequence[int] = (5, 10)) -> Dict[str, float]:
    """Mean metrics over queries.

    ``recall@k``  fraction of a query's relevant items found in the top k (equals hit-rate when one item is relevant)
    ``hit@k``     1 if any relevant item is in the top k (the binary reading of Recall@k)
    ``mrr@10``    reciprocal rank of the first relevant item within the top 10
    ``ndcg@k``    binary-relevance nDCG
    Queries without relevant items are rejected because they would silently deflate the scores.
    """
    if len(rankings) != len(relevant):
        raise ValueError("rankings and relevant sets must have equal length")
    if not rankings:
        raise ValueError("at least one query is required")
    if any(not targets for targets in relevant):
        raise ValueError("every query needs at least one relevant item")
    n = len(rankings)
    out: Dict[str, float] = {}
    for k in ks:
        out[f"recall@{k}"] = sum(len(set(items[:k]) & t) / len(t) for items, t in zip(rankings, relevant)) / n
        out[f"hit@{k}"] = sum(bool(set(items[:k]) & t) for items, t in zip(rankings, relevant)) / n
        out[f"ndcg@{k}"] = sum(_ndcg(items, t, k) for items, t in zip(rankings, relevant)) / n
    out["mrr@10"] = sum(_reciprocal_rank(items[:10], t) for items, t in zip(rankings, relevant)) / n
    return {key: round(value, 5) for key, value in out.items()}
=======
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
>>>>>>> origin/main
