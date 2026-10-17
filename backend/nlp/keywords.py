<<<<<<< HEAD
"""TF-IDF keyword extraction over a paper's chunks (sparse lexical representation)."""
from __future__ import annotations

import re
from typing import Dict, List, Sequence


def extract_keywords(text: str, limit: int = 15, documents: Sequence[str] | None = None) -> List[Dict[str, object]]:
    """Rank terms by TF-IDF. ``documents`` (e.g. a paper's chunks) supplies the IDF corpus.

    Falls back to plain term frequency when scikit-learn is unavailable or the corpus is
    a single document. Output: ``{keyword, score, count}``.
    """
    count_source = text if text else " ".join(documents or [])
    token_re = r"(?u)\b[A-Za-z][A-Za-z0-9_-]{2,}\b"
    docs = [d for d in (documents or []) if d and d.strip()]
    try:
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    except ImportError:
        return _frequency_keywords(count_source, limit)
    if len(docs) < 2:
        docs = [count_source] if count_source.strip() else []
    if not docs:
        return []
    try:
        from sklearn.feature_extraction.text import CountVectorizer

        vectorizer = CountVectorizer(stop_words=list(ENGLISH_STOP_WORDS | {"et", "al", "fig", "figure", "table", "using", "used", "also", "paper"}),
                                     token_pattern=token_re, ngram_range=(1, 2), lowercase=True, max_features=20000)
        counts = vectorizer.fit_transform(docs)
    except ValueError:  # empty vocabulary
        return []
    import numpy as np

    n_docs = counts.shape[0]
    total_tf = np.asarray(counts.sum(axis=0)).ravel()
    doc_freq = np.asarray((counts > 0).sum(axis=0)).ravel()
    # TF-IDF over the paper's chunks: sublinear total frequency x smoothed IDF (terms in every chunk score ~0).
    scores = (1 + np.log(np.maximum(total_tf, 1))) * np.log((n_docs + 1) / (doc_freq + 0.5))
    terms = vectorizer.get_feature_names_out()
    lowered = count_source.lower()
    ranked = sorted(zip(terms, scores), key=lambda item: (-item[1], item[0]))
    out: List[Dict[str, object]] = []
    for term, score in ranked:
        if len(out) >= limit:
            break
        if " " in term and any(set(term.split()) & set(str(k["keyword"]).split()) for k in out if " " in str(k["keyword"])):
            continue
        out.append({"keyword": term, "score": round(float(score), 5), "count": len(re.findall(re.escape(term), lowered))})
    return out


def _frequency_keywords(text: str, limit: int) -> List[Dict[str, object]]:
    from collections import Counter

    stop = frozenset("a an and are as at be by for from has have in into is it of on or that the this to using we with".split())
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text) if w.lower() not in stop]
    counts = Counter(words)
    return [{"keyword": t, "score": round(c / max(len(words), 1), 5), "count": c} for t, c in counts.most_common(limit)]
=======
"""Dependency-light keyword extraction suitable for research-paper text."""
from collections import Counter
import re

_STOP = frozenset("a an and are as at be by for from has have in into is it of on or that the this to using we with".split())


def extract_keywords(text: str, limit: int = 15) -> list[dict[str, object]]:
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text) if w.lower() not in _STOP]
    counts = Counter(words)
    return [{"keyword": term, "score": round(count / max(len(words), 1), 5), "count": count}
            for term, count in counts.most_common(limit)]
>>>>>>> origin/main
