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


if __name__ == "__main__":
    main()
