"""Dependency-light keyword extraction suitable for research-paper text."""
from collections import Counter
import re

_STOP = frozenset("a an and are as at be by for from has have in into is it of on or that the this to using we with".split())


def extract_keywords(text: str, limit: int = 15) -> list[dict[str, object]]:
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text) if w.lower() not in _STOP]
    counts = Counter(words)
    return [{"keyword": term, "score": round(count / max(len(words), 1), 5), "count": count}
            for term, count in counts.most_common(limit)]
