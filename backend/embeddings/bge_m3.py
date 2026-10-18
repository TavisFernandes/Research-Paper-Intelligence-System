"""BGE-M3 dense (and optional sparse) encoder with cached model loading.

Backends, tried in order:
1. ``FlagEmbedding.BGEM3FlagModel``  - dense + BGE-M3 lexical (sparse) weights.
2. ``sentence_transformers``         - dense only (CLS pooling, same vector space).
3. Hashing fallback                  - NOT semantic; only when ``ALLOW_HASHING_FALLBACK`` is true.

``EMBEDDING_MODEL`` may point to a fine-tuned local checkpoint directory.
Vectors are L2-normalised so cosine similarity equals the dot product.
"""
from __future__ import annotations

import logging
import math
import re
import threading
from hashlib import blake2b
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from config import settings
from errors import EmbeddingError

logger = logging.getLogger(__name__)


def _normalise(vector: Sequence[float]) -> List[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if not math.isfinite(norm) or norm == 0:
        return [0.0] * len(vector)
    return [float(v) / norm for v in vector]


def _resolve_device(preference: str) -> str:
    if preference not in ("", "auto"):
        return preference
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


class BgeM3Embedder:
    def __init__(self, model_name: Optional[str] = None, dimensions: Optional[int] = None):
        self.model_name = model_name or settings.embedding_model
        self._hash_dimensions = dimensions or settings.hashing_dimensions
        self._model: Any = None
        self._lock = threading.Lock()
        self._loaded = False
        self.backend = "not-loaded"
        self.device = "cpu"
        self.load_error: Optional[str] = None
        self._dimension: Optional[int] = None

    # ------------------------------------------------------------------ loading
    def _load(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self.device = _resolve_device(settings.embedding_device)
            errors: List[str] = []
            use_fp16 = self.device == "cuda"
            try:
                from FlagEmbedding import BGEM3FlagModel

                self._model = BGEM3FlagModel(self.model_name, use_fp16=use_fp16, device=self.device)
                self.backend = "bge-m3:flagembedding"
            except Exception as exc:
                errors.append(f"FlagEmbedding: {type(exc).__name__}")
                try:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self.model_name, device=self.device)
                    self._model.max_seq_length = settings.embedding_max_length
                    if use_fp16:
                        self._model.half()
                    self.backend = "bge-m3:sentence-transformers"
                except Exception as exc2:
                    errors.append(f"sentence-transformers: {type(exc2).__name__}")
            if self._model is None:
                self.load_error = "; ".join(errors)
                if not settings.allow_hashing_fallback:
                    self._loaded = True
                    raise EmbeddingError(
                        f"Could not load embedding model '{self.model_name}' ({self.load_error}). "
                        "Install FlagEmbedding or sentence-transformers and ensure the model can be downloaded."
                    )
                logger.warning("Embedding model unavailable (%s); using NON-SEMANTIC hashing embeddings.", self.load_error)
                self.backend = "hashing"
                self.device = "cpu"
            self._loaded = True

    # ----------------------------------------------------------------- properties
    @property
    def is_semantic(self) -> bool:
        self._load()
        return self.backend != "hashing"

    @property
    def dimension(self) -> int:
        self._load()
        if self.backend == "hashing":
            return self._hash_dimensions
        if self._dimension is None:
            self._dimension = len(self.encode("dimension probe"))
        return self._dimension

    def status(self) -> Dict[str, object]:
        """Cheap status (never triggers model loading)."""
        return {"model": self.model_name, "backend": self.backend, "device": self.device, "loaded": self._loaded,
                "semantic": self.backend not in ("hashing", "not-loaded"), "load_error": self.load_error,
                "note": "Model loads on first use." if not self._loaded else None}

    # ------------------------------------------------------------------- encoding
    def _hash_embed(self, text: str) -> List[float]:
        vector = [0.0] * self._hash_dimensions
        tokens = re.findall(r"\w+", text.lower())
        for token in tokens or ["<empty>"]:
            value = int.from_bytes(blake2b(token.encode(), digest_size=8).digest(), "little")
            vector[value % self._hash_dimensions] += -1.0 if value & 1 else 1.0
        return _normalise(vector)

    def encode(self, texts: str | Iterable[str]) -> List[float] | List[List[float]]:
        """Encode one string (returns a vector) or many (returns a list of vectors)."""
        single = isinstance(texts, str)
        values = [texts] if single else list(texts)
        if not values:
            return []
        self._load()
        with self._lock:
            if self.backend == "hashing":
                vectors = [self._hash_embed(v) for v in values]
            elif self.backend == "bge-m3:flagembedding":
                out = self._model.encode(values, batch_size=settings.embedding_batch_size, max_length=settings.embedding_max_length,
                                         return_dense=True, return_sparse=False, return_colbert_vecs=False)
                vectors = [_normalise(v) for v in out["dense_vecs"].tolist()]
            else:
                vectors = [_normalise(v) for v in self._model.encode(values, batch_size=settings.embedding_batch_size,
                                                                      normalize_embeddings=True, show_progress_bar=False).tolist()]
        return vectors[0] if single else vectors

    def encode_with_sparse(self, texts: Sequence[str]) -> Tuple[List[List[float]], List[Optional[Dict[str, float]]]]:
        """Dense vectors plus BGE-M3 lexical weights (``None`` entries when unsupported)."""
        self._load()
        if self.backend != "bge-m3:flagembedding":
            return self.encode(list(texts)), [None] * len(texts)  # type: ignore[return-value]
        with self._lock:
            out = self._model.encode(list(texts), batch_size=settings.embedding_batch_size, max_length=settings.embedding_max_length,
                                     return_dense=True, return_sparse=True, return_colbert_vecs=False)
            dense = [_normalise(v) for v in out["dense_vecs"].tolist()]
            sparse = [{str(k): round(float(w), 5) for k, w in item.items()} for item in out["lexical_weights"]]
        return dense, sparse

    @staticmethod
    def sparse_terms(text: str) -> Dict[str, float]:
        """Simple normalised term frequencies (used when BGE-M3 sparse weights are unavailable)."""
        terms = re.findall(r"\w+", text.lower())
        if not terms:
            return {}
        return {term: terms.count(term) / len(terms) for term in set(terms)}


_embedder: Optional[BgeM3Embedder] = None
_embedder_lock = threading.Lock()


def get_embedder() -> BgeM3Embedder:
    """Process-wide embedder (the model is loaded once, lazily)."""
    global _embedder
    with _embedder_lock:
        if _embedder is None:
            _embedder = BgeM3Embedder()
        return _embedder


def set_embedder(instance: Optional[BgeM3Embedder]) -> None:
    """Replace the shared embedder (tests, switching to a fine-tuned checkpoint)."""
    global _embedder
    with _embedder_lock:
        _embedder = instance
