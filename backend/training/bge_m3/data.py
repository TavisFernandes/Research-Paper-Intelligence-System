"""Training/evaluation data preparation for BGE-M3 retrieval fine-tuning (pure Python, unit-tested).

PubMedQA records contain a question, a context made of abstract paragraphs and an answer. They do NOT
come with explicit retrieval labels, so pairs are *constructed*:

* query    = the PubMedQA question
* positive = the abstract context of that question (``granularity="abstract"``, default) or one
             paragraph of it (``granularity="paragraph"``, weak labels: every paragraph is treated as relevant)
* negatives= contexts of *other* questions, mined with BM25 (hard) plus random (easy)

Limitations (also in the README): PubMedQA questions are derived from abstracts, so "relevant" means
"the abstract the question was written for", not human-annotated passage relevance in full papers.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


def passages_from_record(record: Dict[str, Any], granularity: str = "abstract") -> List[str]:
    context = record.get("context", record)
    paragraphs = context.get("contexts") if isinstance(context, dict) else None
    paragraphs = [str(p).strip() for p in (paragraphs or []) if str(p).strip()]
    if not paragraphs:
        return []
    if granularity == "paragraph":
        return paragraphs
    if granularity != "abstract":
        raise ValueError("granularity must be 'abstract' or 'paragraph'")
    return [" ".join(paragraphs)]


def build_pairs(records: Iterable[Dict[str, Any]], granularity: str = "abstract", n_negatives: int = 3, hard_negatives: bool = True,
                seed: int = 42, max_records: Optional[int] = None) -> List[Dict[str, Any]]:
    """Construct ``{id, query, positive, negatives}`` rows. Deterministic for a fixed ``seed``."""
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for record in records:
        question = str(record.get("question", "")).strip()
        passages = passages_from_record(record, granularity)
        if not question or not passages:
            continue
        for index, passage in enumerate(passages):
            rows.append({"id": f"{record.get('pubid', len(rows))}:{index}", "group": str(record.get("pubid", len(rows))),
                         "query": question, "positive": passage, "negatives": []})
        if max_records and len({r["group"] for r in rows}) >= max_records:
            break
    if not rows or n_negatives <= 0:
        return rows
    pool = [(r["group"], r["positive"]) for r in rows]
    bm25 = None
    if hard_negatives:
        from retrieval.lexical import BM25Index

        bm25 = BM25Index([{"text": text, "chunk_id": str(i), "paper_id": group} for i, (group, text) in enumerate(pool)])
    for row in rows:
        negatives: List[str] = []
        if bm25 is not None:
            for hit in bm25.search(row["query"], limit=n_negatives * 4):
                if hit["paper_id"] != row["group"] and hit["text"] not in negatives:
                    negatives.append(hit["text"])
                if len(negatives) >= max(1, n_negatives - 1):
                    break
        attempts = 0
        while len(negatives) < n_negatives and attempts < 50 and len(pool) > 1:
            attempts += 1
            group, text = rng.choice(pool)
            if group != row["group"] and text not in negatives:
                negatives.append(text)
        row["negatives"] = negatives[:n_negatives]
    return rows


def split_by_group(rows: Sequence[Dict[str, Any]], val_fraction: float = 0.1, seed: int = 42) -> Dict[str, List[Dict[str, Any]]]:
    """Train/validation split by *question group* so no question (or its abstract) appears in both."""
    groups = sorted({r["group"] for r in rows})
    random.Random(seed).shuffle(groups)
    n_val = max(1, int(len(groups) * val_fraction)) if len(groups) > 1 else 0
    val_groups = set(groups[:n_val])
    return {"train": [r for r in rows if r["group"] not in val_groups], "validation": [r for r in rows if r["group"] in val_groups]}


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
