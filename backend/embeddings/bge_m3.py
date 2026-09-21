"""BGE-M3 encoder with a deterministic hashing fallback for offline development."""
from __future__ import annotations
from hashlib import blake2b
import math
import re
from typing import Iterable
from config import settings


class BgeM3Embedder:
    def __init__(self, model_name: str = settings.embedding_model, dimensions: int = 384):
        self.model_name, self.dimensions, self._model = model_name, dimensions, None
        self.backend = "hashing"

    def _load(self) -> None:
        if self._model is not None or self.backend == "unavailable":
            return
        try:
            from FlagEmbedding import BGEM3FlagModel
            self._model = BGEM3FlagModel(self.model_name, use_fp16=False)
            self.backend = "bge-m3"
        except Exception:
            self.backend = "hashing"

    def _hash_embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in re.findall(r"\w+", text.lower()):
            digest = blake2b(token.encode(), digest_size=8).digest()
            value = int.from_bytes(digest, "little")
            vector[value % self.dimensions] += -1.0 if value & 1 else 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def encode(self, texts: str | Iterable[str]) -> list[float] | list[list[float]]:
        single = isinstance(texts, str)
        values = [texts] if single else list(texts)
        self._load()
        if self._model is not None:
            output = self._model.encode(values, return_dense=True, return_sparse=False, return_colbert_vecs=False)
            vectors = output["dense_vecs"].tolist()
        else:
            vectors = [self._hash_embed(value) for value in values]
        return vectors[0] if single else vectors

    def sparse_terms(self, text: str) -> dict[str, float]:
        terms = re.findall(r"\w+", text.lower())
        return {term: terms.count(term) / len(terms) for term in set(terms)} if terms else {}


embedder = BgeM3Embedder()
