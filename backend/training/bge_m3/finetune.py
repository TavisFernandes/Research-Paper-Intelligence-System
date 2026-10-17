<<<<<<< HEAD
"""Contrastive fine-tuning of BGE-M3 for scientific retrieval (query, positive[, hard negatives]).

Objective: MultipleNegativesRankingLoss (InfoNCE) - every other positive/negative in the batch is a negative.
Resource-efficient options (BGE-M3 has ~568M parameters):
  --cached-mini-batch N   CachedMultipleNegativesRankingLoss (GradCache): large effective batch with small memory
  --freeze-embeddings     freeze the 250k-token embedding matrix (~45% of the parameters)
  --gradient-checkpointing, --max-seq-length, --bf16/--fp16
This fine-tunes the dense embedding head only; BGE-M3's sparse/ColBERT heads are not trained here.
Training is NOT run by the test-suite and no fine-tuned weights ship with the repository.

    python -m training.bge_m3.finetune --train data/bge_m3/train.jsonl --val data/bge_m3/validation.jsonl --output checkpoints/bge-m3-sci
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from .data import read_jsonl


def build_columns(rows: List[Dict[str, Any]], use_negatives: bool) -> Dict[str, List[str]]:
    """Convert JSONL rows to trainer columns (anchor/positive[/negative]); drops rows without a negative when required."""
    usable = [r for r in rows if r.get("query") and r.get("positive")]
    if use_negatives:
        usable = [r for r in usable if r.get("negatives")]
        return {"anchor": [r["query"] for r in usable], "positive": [r["positive"] for r in usable], "negative": [r["negatives"][0] for r in usable]}
    return {"anchor": [r["query"] for r in usable], "positive": [r["positive"] for r in usable]}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--train", type=Path, required=True)
    p.add_argument("--val", type=Path, default=None)
    p.add_argument("--base-model", default="BAAI/bge-m3")
    p.add_argument("--output", type=Path, default=Path("checkpoints/bge-m3-scientific"))
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--learning-rate", type=float, default=1e-5)
    p.add_argument("--warmup-ratio", type=float, default=0.1)
    p.add_argument("--max-seq-length", type=int, default=512)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-hard-negatives", action="store_true")
    p.add_argument("--cached-mini-batch", type=int, default=0)
    p.add_argument("--freeze-embeddings", action="store_true")
    p.add_argument("--gradient-checkpointing", action="store_true")
    p.add_argument("--fp16", action="store_true")
    p.add_argument("--bf16", action="store_true")
    p.add_argument("--save-steps", type=int, default=500)
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        import torch
        from datasets import Dataset
        from sentence_transformers import SentenceTransformer, SentenceTransformerTrainer, SentenceTransformerTrainingArguments, losses
        from sentence_transformers.training_args import BatchSamplers
        from transformers import set_seed
    except ImportError as exc:
        raise SystemExit("Fine-tuning needs: pip install -r requirements-training.txt (torch, sentence-transformers>=3, datasets, accelerate)") from exc
    set_seed(args.seed)
    use_neg = not args.no_hard_negatives
    train_cols = build_columns(read_jsonl(args.train), use_neg)
    if not train_cols["anchor"]:
        raise SystemExit("No usable training rows (need 'query' and 'positive'" + (" and 'negatives'" if use_neg else "") + ").")
    train_ds = Dataset.from_dict(train_cols)
    eval_ds = Dataset.from_dict(build_columns(read_jsonl(args.val), use_neg)) if args.val else None
    model = SentenceTransformer(args.base_model)
    model.max_seq_length = args.max_seq_length
    if args.gradient_checkpointing:
        model[0].auto_model.gradient_checkpointing_enable()
    if args.freeze_embeddings:
        for param in model[0].auto_model.embeddings.word_embeddings.parameters():
            param.requires_grad = False
    loss = (losses.CachedMultipleNegativesRankingLoss(model, mini_batch_size=args.cached_mini_batch) if args.cached_mini_batch
            else losses.MultipleNegativesRankingLoss(model))
    training_args = SentenceTransformerTrainingArguments(
        output_dir=str(args.output), num_train_epochs=args.epochs, per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size, learning_rate=args.learning_rate, warmup_ratio=args.warmup_ratio,
        fp16=args.fp16, bf16=args.bf16, batch_sampler=BatchSamplers.NO_DUPLICATES, seed=args.seed, data_seed=args.seed,
        eval_strategy="steps" if eval_ds is not None else "no", eval_steps=args.save_steps, save_strategy="steps", save_steps=args.save_steps,
        save_total_limit=2, logging_steps=25, report_to="none", load_best_model_at_end=eval_ds is not None,
    )
    trainer = SentenceTransformerTrainer(model=model, args=training_args, train_dataset=train_ds, eval_dataset=eval_ds, loss=loss)
    result = trainer.train()
    args.output.mkdir(parents=True, exist_ok=True)
    model.save(str(args.output / "final"))
    report = {"args": {k: str(v) for k, v in vars(args).items()}, "train_rows": len(train_ds), "val_rows": len(eval_ds) if eval_ds is not None else 0,
              "train_loss": result.training_loss, "log_history": trainer.state.log_history[-20:], "torch": torch.__version__,
              "device": "cuda" if torch.cuda.is_available() else "cpu",
              "note": "Only evaluate claims after running training.bge_m3.compare on held-out data."}
    (args.output / "training_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"Saved checkpoint to {args.output / 'final'}", file=sys.stderr)
=======
"""Optional BGE-M3 fine-tuning entry point using JSONL {query, positive} records."""
import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    args = parser.parse_args()
    pairs = [json.loads(line) for line in args.data.read_text(encoding="utf-8").splitlines() if line.strip()]
    try:
        from sentence_transformers import InputExample, SentenceTransformer, losses
        from torch.utils.data import DataLoader
        model = SentenceTransformer("BAAI/bge-m3")
        loader = DataLoader([InputExample(texts=[item["query"], item["positive"]]) for item in pairs], shuffle=True, batch_size=8)
        model.fit(train_objectives=[(loader, losses.MultipleNegativesRankingLoss(model))], epochs=1, warmup_steps=max(1, len(loader)//10))
        model.save("bge-m3-research-finetuned")
    except ImportError as error:
        raise SystemExit("Install sentence-transformers and torch to fine-tune BGE-M3.") from error
>>>>>>> origin/main


if __name__ == "__main__":
    main()
