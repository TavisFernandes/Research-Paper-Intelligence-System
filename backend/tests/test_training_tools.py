import numpy as np
import pytest

from training.bge_m3.compare import build_eval_set, evaluate_encoder
from training.bge_m3.data import build_pairs, passages_from_record, read_jsonl, split_by_group, write_jsonl
from training.bge_m3.finetune import build_columns, parse_args


def records(n=20):
    topics = ["aspirin", "insulin", "statin", "vaccine", "antibiotic"]
    return [{"pubid": 1000 + i, "question": f"Does {topics[i % 5]} treatment {i} improve outcome?",
             "context": {"contexts": [f"Patients received {topics[i % 5]} treatment {i} in a trial.", f"Outcome {i} was measured after {i} weeks."]}} for i in range(n)]


def test_passages_granularity():
    r = records(1)[0]
    assert len(passages_from_record(r, "abstract")) == 1 and len(passages_from_record(r, "paragraph")) == 2
    assert passages_from_record({"question": "q", "context": {"contexts": []}}) == []
    with pytest.raises(ValueError):
        passages_from_record(r, "weird")


def test_pairs_have_valid_negatives_and_are_deterministic():
    a, b = build_pairs(records(), n_negatives=3, seed=7), build_pairs(records(), n_negatives=3, seed=7)
    assert a == b and len(a) == 20
    for row in a:
        assert row["positive"] not in row["negatives"] and len(row["negatives"]) == 3 and len(set(row["negatives"])) == 3
        assert row["query"] and row["id"]


def test_split_has_no_group_leakage_and_is_reproducible():
    rows = build_pairs(records(), granularity="paragraph")
    s1, s2 = split_by_group(rows, 0.2, seed=1), split_by_group(rows, 0.2, seed=1)
    assert s1 == s2 and s1["validation"] and s1["train"]
    assert not {r["group"] for r in s1["train"]} & {r["group"] for r in s1["validation"]}
    assert len(s1["train"]) + len(s1["validation"]) == len(rows)


def test_jsonl_roundtrip(tmp_path):
    rows = build_pairs(records(3))
    assert write_jsonl(tmp_path / "x" / "t.jsonl", rows) == 3 and read_jsonl(tmp_path / "x" / "t.jsonl") == rows


def test_trainer_columns_and_args():
    rows = build_pairs(records(6))
    with_neg = build_columns(rows, True)
    assert set(with_neg) == {"anchor", "positive", "negative"} and len(with_neg["anchor"]) == 6
    assert set(build_columns(rows, False)) == {"anchor", "positive"}
    assert build_columns([{"query": "q", "positive": "p", "negatives": []}], True)["anchor"] == []  # row without negative dropped
    args = parse_args(["--train", "t.jsonl", "--freeze-embeddings", "--cached-mini-batch", "8", "--seed", "3"])
    assert args.freeze_embeddings and args.cached_mini_batch == 8 and args.seed == 3 and args.base_model == "BAAI/bge-m3"


def test_encoder_comparison_uses_identical_data_and_detects_better_model():
    rows = build_pairs(records(20), n_negatives=2)
    eval_set = build_eval_set(rows)
    vocab = {}

    def lexical_encoder(texts):
        out = np.zeros((len(texts), 512), dtype=np.float32)
        for i, t in enumerate(texts):
            for w in t.lower().replace("?", "").replace(".", "").split():
                out[i, vocab.setdefault(w, len(vocab) % 512)] += 1
        return out

    rng = np.random.default_rng(0)  # shared, so queries and documents get different random vectors

    def random_encoder(texts):
        return rng.normal(size=(len(texts), 64)).astype(np.float32)

    good, bad = evaluate_encoder(lexical_encoder, eval_set), evaluate_encoder(random_encoder, eval_set)
    assert good["mrr@10"] > bad["mrr@10"] and set(good) >= {"recall@5", "recall@10", "mrr@10", "ndcg@10"}
    assert len(eval_set["queries"]) == 20 and eval_set["corpus"]
