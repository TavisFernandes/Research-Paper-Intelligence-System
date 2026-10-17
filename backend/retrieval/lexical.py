"""BM25 lexical index (sparse retrieval) built over stored chunks. No external dependency."""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pdf_processing.preprocess import _rule_lemma, tokenize_text

_STOP = frozenset(
    "a an and are as at be been being by can could did do does for from had has have how in into is it its of on or our that the their "
    "there these this those to was we were what when where which who whom why will with would about than then they them you your".split()
)


def lexical_tokens(text: str) -> List[str]:
    """Lower-cased, stop-word-free, lightly lemmatised tokens (identical for index and query)."""
    out = []
    for token in tokenize_text(text.lower()):
        token = token.strip("'")
        if len(token) < 2 or token in _STOP:
            continue
        out.append(_rule_lemma(token))
    return out


class BM25Index:
    def __init__(self, chunks: Sequence[Dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.chunks = list(chunks)
        self.doc_tokens = [lexical_tokens(str(c.get("text", ""))) for c in self.chunks]
        self.term_freqs = [Counter(tokens) for tokens in self.doc_tokens]
        self.lengths = [len(tokens) for tokens in self.doc_tokens]
        self.avg_length = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        doc_freq: Counter = Counter()
        for freqs in self.term_freqs:
            doc_freq.update(freqs.keys())
        n = len(self.chunks)
        self.idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in doc_freq.items()}

    def search(self, query: str, limit: int = 20, paper_ids: Optional[Sequence[str]] = None,
               section_names: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
        terms = list(dict.fromkeys(lexical_tokens(query)))
        if not terms or not self.chunks:
            return []
        scored: List[Tuple[float, int]] = []
        for index, chunk in enumerate(self.chunks):
            if paper_ids and chunk.get("paper_id") not in paper_ids:
                continue
            if section_names and chunk.get("section_name") not in section_names:
                continue
            freqs, length = self.term_freqs[index], self.lengths[index]
            score = 0.0
            for term in terms:
                tf = freqs.get(term, 0)
                if tf:
                    denom = tf + self.k1 * (1 - self.b + self.b * length / (self.avg_length or 1.0))
                    score += self.idf.get(term, 0.0) * tf * (self.k1 + 1) / denom
            if score > 0:
                scored.append((score, index))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [{**self.chunks[i], "bm25": round(score, 5)} for score, i in scored[:limit]]

    def coverage(self, query: str, chunk_text: str) -> float:
        terms = set(lexical_tokens(query))
        if not terms:
            return 0.0
        present = set(lexical_tokens(chunk_text))
        return len(terms & present) / len(terms)
