"""Build retrieval training/validation JSONL files from PubMedQA (Hugging Face ``qiaojin/PubMedQA``).

Example:
    python -m training.bge_m3.prepare_pubmedqa --config pqa_labeled --out data/bge_m3 --max-records 5000
Requires ``pip install datasets`` and internet access to the Hugging Face Hub (MIT-licensed dataset).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .data import build_pairs, split_by_group, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="pqa_labeled", help="pqa_labeled (1k, expert), pqa_artificial (211k), pqa_unlabeled")
    parser.add_argument("--split", default="train")
    parser.add_argument("--out", type=Path, default=Path("data/bge_m3"))
    parser.add_argument("--granularity", choices=["abstract", "paragraph"], default="abstract")
    parser.add_argument("--negatives", type=int, default=3)
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--max-records", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit("Install the 'datasets' package (pip install datasets) to download PubMedQA.") from exc
    dataset = load_dataset("qiaojin/PubMedQA", args.config, split=args.split)
    rows = build_pairs((dict(r) for r in dataset), args.granularity, args.negatives, True, args.seed, args.max_records)
    splits = split_by_group(rows, args.val_fraction, args.seed)
    counts = {name: write_jsonl(args.out / f"{name}.jsonl", items) for name, items in splits.items()}
    (args.out / "data_card.json").write_text(json.dumps({"source": "qiaojin/PubMedQA", "config": args.config, "split": args.split,
                                                          "granularity": args.granularity, "negatives": args.negatives, "seed": args.seed,
                                                          "counts": counts, "note": "Pairs are constructed, not human-labelled retrieval judgements."}, indent=2))
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
