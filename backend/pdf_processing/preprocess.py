import re
from typing import List


def clean_text(text: str) -> str:
    """Normalize whitespace while preserving the extracted words and order."""
    text = text.replace("\u00ad", "")
    text = re.sub(r"(?<=\w)-\s+(?=\w)", "", text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def segment_sentences(text: str) -> List[str]:
    cleaned = clean_text(text)
    if not cleaned:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", cleaned) if part.strip()]


def tokenize_text(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*'?", text)


def lemmatize_tokens(tokens: List[str]) -> List[str]:
    """Apply a deterministic lightweight lemmatization fallback.

    A trained lemmatizer can replace this function later without changing the
    pipeline contract.
    """
    lemmas: List[str] = []
    for token in tokens:
        lower = token.lower()
        if len(lower) > 5 and lower.endswith("ies"):
            lower = lower[:-3] + "y"
        elif len(lower) > 4 and lower.endswith("ing"):
            lower = lower[:-3]
        elif len(lower) > 4 and lower.endswith("ed"):
            lower = lower[:-2]
        elif len(lower) > 3 and lower.endswith("s") and not lower.endswith("ss"):
            lower = lower[:-1]
        lemmas.append(lower)
    return lemmas
