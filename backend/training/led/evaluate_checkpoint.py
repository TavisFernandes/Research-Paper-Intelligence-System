"""ROUGE evaluation of an LED checkpoint on {"article", "abstract"} JSONL records (e.g. exported from ccdv/pubmed-summarization).

    ENABLE_LED=true LED_MODEL=path/to/checkpoint python -m training.led.evaluate_checkpoint data/led_val.jsonl --limit 50
Reports ROUGE-1/2/L only for what is actually generated; nothing is cached or pre-filled.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from summarization.led import rouge
from summarization.led.service import _led


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("data", type=Path)
    p.add_argument("--limit", type=int, default=50)
    args = p.parse_args()
    records = [json.loads(l) for l in args.data.read_text(encoding="utf-8").splitlines() if l.strip()][: args.limit]
    preds = [_led.summarize(r["article"])["summary"] for r in records]
    print(json.dumps(rouge(preds, [r["abstract"] for r in records]), indent=2))


if __name__ == "__main__":
    main()
