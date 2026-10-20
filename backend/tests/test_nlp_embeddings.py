import math
import sys
from types import ModuleType, SimpleNamespace

import pytest

from config import settings
from embeddings import BgeM3Embedder
from errors import EmbeddingError
from nlp import extract_entities, extract_keywords


def test_entities_are_typed_and_not_fabricated():
    text = "We fine-tune BERT on the SQuAD dataset and report F1 score and Recall@10. Google released it."
    found = {(e["label"], e["text"]) for e in extract_entities(text)}
    assert ("MODEL", "BERT") in found and ("DATASET", "SQuAD") in found and ("METRIC", "Recall@10") in found
    assert not any(label == "DATASET" and value in {"We", "The", "Google"} for label, value in found)
    assert all(e["source"] in {"rule", "spacy", "scispacy"} for e in extract_entities(text))


def test_no_entities_in_plain_prose():
    assert extract_entities("The weather was pleasant and the walk was long.") == []


def test_dataset_cue_pattern():
    found = {e["text"] for e in extract_entities("The model was trained on the Foo Bar dataset for ten epochs.") if e["label"] == "DATASET"}
    assert "Foo Bar" in found


def test_keywords_tfidf_prefers_distinctive_terms():
    docs = ["retrieval retrieval embeddings of papers", "papers about cooking and recipes", "papers about travel plans"]
    kws = extract_keywords(" ".join(docs), limit=5, documents=docs)
    assert kws and kws[0]["keyword"] in {"retrieval", "retrieval embeddings", "embeddings"}
    assert extract_keywords("", limit=5) == []


def test_hashing_embeddings_are_normalised_and_deterministic():
    e = BgeM3Embedder(dimensions=64, force_hashing=True)
    v1, v2 = e.encode("dense retrieval of papers"), e.encode("dense retrieval of papers")
    assert v1 == v2 and len(v1) == 64 and math.isclose(sum(x * x for x in v1), 1.0, rel_tol=1e-6)
    assert e.backend == "hashing" and e.is_semantic is False
    assert len(e.encode(["a b", "c d"])) == 2 and e.encode([]) == []
    assert e.encode("").__len__() == 64  # empty text still yields a valid vector


def test_finetuned_checkpoint_loads_encoder_state_dict(tmp_path, monkeypatch):
    checkpoint = tmp_path / "bge_m3_finetuned.pth"
    checkpoint.touch()
    loaded = {}

    class FakeModel:
        def load_state_dict(self, state_dict):
            loaded["state_dict"] = state_dict

        def to(self, device):
            loaded["device"] = device
            return self

        def eval(self):
            return self

    model = FakeModel()
    transformers = ModuleType("transformers")
    transformers.AutoModel = SimpleNamespace(from_pretrained=lambda name: model)
    transformers.AutoTokenizer = SimpleNamespace(from_pretrained=lambda name: object())
    torch = ModuleType("torch")
    torch.cuda = SimpleNamespace(is_available=lambda: False)
    torch.backends = SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False))
    torch.load = lambda path, map_location, weights_only: {"encoder.weight": "fine-tuned"}
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "torch", torch)

    embedder = BgeM3Embedder(model_name=str(checkpoint))
    embedder._load()

    assert embedder.backend == "bge-m3:finetuned"
    assert loaded["state_dict"] == {"weight": "fine-tuned"}
    assert loaded["device"] == "cpu"


def test_similar_texts_score_higher_than_dissimilar_with_fallback():
    e = BgeM3Embedder(dimensions=256, force_hashing=True)
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    q, near, far = e.encode("fine-tuning retrieval models"), e.encode("fine-tuning of retrieval models helps"), e.encode("banana smoothie recipe")
    assert dot(q, near) > dot(q, far)


def test_missing_model_without_fallback_raises_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "allow_hashing_fallback", False)
    monkeypatch.setattr(settings, "embedding_model", str(tmp_path / "missing.pth"))
    with pytest.raises(EmbeddingError, match="Could not load embedding model"):
        BgeM3Embedder().encode("x")


def test_status_does_not_load_model():
    e = BgeM3Embedder()
    assert e.status()["loaded"] is False and e.backend == "not-loaded"
