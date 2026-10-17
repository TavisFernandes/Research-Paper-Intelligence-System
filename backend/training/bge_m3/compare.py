"""Compare baseline vs fine-tuned retrieval on the SAME held-out data (Recall@5/10, MRR@10, nDCG@10).

Input: validation.jsonl from prepare_pubmedqa (query + positive). The corpus is every distinct positive
plus every negative; a query's relevant document is its own positive.

    python -m training.bge_m3.compare --eval data/bge_m3/validation.jsonl --baseline BAAI/bge-m3 --finetuned checkpoints/bge-m3-sci/final
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence

import numpy as np

from .data import read_jsonl
from .evaluate import evaluate_rankings

EncodeFn = Callable[[Sequence[str]], np.ndarray]


def build_eval_set(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    corpus: List[str] = []
    index: Dict[str, int] = {}

    def add(text: str) -> int:
        if text not in index:
            index[text] = len(corpus)
            corpus.append(text)
        return index[text]

    queries, relevant = [], []
    for row in rows:
        queries.append(row["query"])
        relevant.append({str(add(row["positive"]))})
    for row in rows:
        for negative in row.get("negatives", []):
            add(negative)
    return {"queries": queries, "relevant": relevant, "corpus": corpus}


def evaluate_encoder(encode: EncodeFn, eval_set: Dict[str, Any], top_k: int = 10) -> Dict[str, float]:
    """Rank the corpus with cosine similarity and compute the retrieval metrics."""
    docs = np.asarray(encode(eval_set["corpus"]), dtype=np.float32)
    queries = np.asarray(encode(eval_set["queries"]), dtype=np.float32)
    docs /= np.linalg.norm(docs, axis=1, keepdims=True) + 1e-12
    queries /= np.linalg.norm(queries, axis=1, keepdims=True) + 1e-12
    scores = queries @ docs.T
    rankings = [[str(i) for i in np.argsort(-row)[:top_k]] for row in scores]
    return evaluate_rankings(rankings, eval_set["relevant"])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--eval", type=Path, required=True)
    p.add_argument("--baseline", default="BAAI/bge-m3")
    p.add_argument("--finetuned", required=True)
    p.add_argument("--out", type=Path, default=Path("retrieval_eval_report.json"))
    p.add_argument("--max-queries", type=int, default=None)
    p.add_argument("--batch-size", type=int, default=16)
    args = p.parse_args()
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit("Install sentence-transformers (requirements-training.txt) to run this comparison.") from exc
    rows = read_jsonl(args.eval)[: args.max_queries]
    eval_set = build_eval_set(rows)
    digest = hashlib.sha256(json.dumps([eval_set["queries"], eval_set["corpus"]]).encode()).hexdigest()[:16]
    report: Dict[str, Any] = {"eval_file": str(args.eval), "n_queries": len(eval_set["queries"]), "corpus_size": len(eval_set["corpus"]), "data_hash": digest}
    for name, path in (("baseline", args.baseline), ("finetuned", args.finetuned)):
        model = SentenceTransformer(path)
        report[name] = {"model": path, **evaluate_encoder(lambda t, m=model: m.encode(list(t), batch_size=args.batch_size, normalize_embeddings=True), eval_set)}
    report["delta"] = {k: round(report["finetuned"][k] - report["baseline"][k], 5) for k in report["baseline"] if k != "model"}
    args.out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
