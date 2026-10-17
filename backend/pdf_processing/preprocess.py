<<<<<<< HEAD
<<<<<<< HEAD
"""NLP preprocessing with spaCy (cleaning, sentence segmentation, tokenisation, lemmatisation).

The text is normalised conservatively: numbers, citations ("[12]", "Smith et al., 2020"),
equations and hyphenated scientific terms are left intact. Missing spaCy models degrade
to documented rule-based fallbacks and are reported through :func:`nlp_status`.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

SPACY_MODEL = "en_core_web_sm"
SETUP_HINT = f"python -m spacy download {SPACY_MODEL}"

_LIGATURES = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl", "\u00ad": ""}
_ABBREVIATIONS = ("et al.", "e.g.", "i.e.", "Fig.", "Figs.", "Eq.", "Eqs.", "Tab.", "Sec.", "Ref.", "vs.", "cf.", "No.", "approx.", "resp.", "Dr.", "Prof.")


def clean_text(text: str) -> str:
    """Normalise whitespace and PDF artefacts while preserving scientific content."""
    for source, target in _LIGATURES.items():
        text = text.replace(source, target)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    # Re-join words hyphenated across a line break ("classi-\nfication"), but keep real compounds.
    text = re.sub(r"(?<=[a-z])-\n(?=[a-z])", "", text)
    lines = [re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


@lru_cache(maxsize=1)
def _load_nlp() -> Tuple[Any, str]:
    """Load the spaCy pipeline once. Returns (nlp, status)."""
    try:
        import spacy
    except ImportError:
        logger.warning("spaCy is not installed; using rule-based preprocessing. pip install spacy && %s", SETUP_HINT)
        return None, "unavailable: spaCy not installed"
    try:
        nlp = spacy.load(SPACY_MODEL, disable=["ner"])
        nlp.max_length = max(nlp.max_length, 3_000_000)
        return nlp, f"spacy:{SPACY_MODEL}"
    except OSError:
        logger.warning("spaCy model '%s' not found. Install it with: %s", SPACY_MODEL, SETUP_HINT)
        nlp = spacy.blank("en")
        nlp.add_pipe("sentencizer")
        return nlp, f"blank-en+sentencizer (model missing; run: {SETUP_HINT})"


def nlp_status() -> Dict[str, object]:
    nlp, status = _load_nlp()
    return {"backend": status, "has_lemmatizer": bool(nlp is not None and "lemmatizer" in nlp.pipe_names), "setup_hint": SETUP_HINT}


def _flatten(text: str) -> str:
    """Replace newlines by spaces 1:1 so character offsets remain valid."""
    return text.replace("\n", " ")


def _regex_sentence_spans(flat: str) -> List[Tuple[int, int]]:
    protected = flat
    for abbreviation in _ABBREVIATIONS:
        protected = protected.replace(abbreviation, abbreviation.replace(".", "\u2024"))
    protected = re.sub(r"(?<=\d)\.(?=\d)", "\u2024", protected)
    spans: List[Tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])", protected):
        if match.start() > start:
            spans.append((start, match.start()))
        start = match.end()
    if start < len(flat):
        spans.append((start, len(flat)))
    return [(s, e) for s, e in spans if flat[s:e].strip()]


def segment_sentence_spans(text: str) -> List[Tuple[int, int]]:
    """Return (start, end) character offsets of each sentence in ``text`` (newlines = spaces)."""
    flat = _flatten(text)
    if not flat.strip():
        return []
    nlp, _ = _load_nlp()
    if nlp is None:
        return _regex_sentence_spans(flat)
    try:
        spans = [(s.start_char, s.end_char) for s in nlp(flat).sents if s.text.strip()]
    except Exception:
        logger.exception("spaCy sentence segmentation failed; using regex fallback")
        return _regex_sentence_spans(flat)
    return spans


def segment_sentences(text: str) -> List[str]:
    cleaned = clean_text(text)
    flat = _flatten(cleaned)
    return [flat[start:end].strip() for start, end in segment_sentence_spans(cleaned)]


def tokenize_text(text: str) -> List[str]:
    """Tokenise keeping decimals, hyphenated terms (CIFAR-10, F1-score) and apostrophes."""
    return re.findall(r"[A-Za-z0-9]+(?:[.\-_'][A-Za-z0-9]+)*'?", text)


def _rule_lemma(token: str) -> str:
    lower = token.lower()
    if len(lower) > 4 and lower.endswith("ies"):
        return lower[:-3] + "y"
    if len(lower) > 5 and lower.endswith("ing"):
        stem = lower[:-3]
        if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "aeioulsz":
            stem = stem[:-1]
        return stem
    if len(lower) > 4 and lower.endswith("ed"):
        stem = lower[:-2]
        return stem[:-1] if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "aeioulsz" else stem
    if len(lower) > 3 and lower.endswith("s") and not lower.endswith(("ss", "us", "is")):
        return lower[:-1]
    return lower


def lemmatize_tokens(tokens: List[str]) -> List[str]:
    """Lemmatise pre-tokenised text, one lemma per token (alignment preserved)."""
    if not tokens:
        return []
    nlp, _ = _load_nlp()
    if nlp is not None and "lemmatizer" in nlp.pipe_names:
        try:
            from spacy.tokens import Doc

            doc = Doc(nlp.vocab, words=list(tokens))
            for _, component in nlp.pipeline:
                doc = component(doc)
            return [(token.lemma_ or token.text).lower() for token in doc]
        except Exception:
            logger.exception("spaCy lemmatisation failed; using rule-based fallback")
    return [_rule_lemma(token) for token in tokens]


def preprocess_text(text: str) -> Dict[str, List[str]]:
    """Full preprocessing of a text: sentences, tokens and lemmas."""
    sentences = segment_sentences(text)
    tokens = tokenize_text(text)
    return {"sentences": sentences, "tokens": tokens, "lemmas": lemmatize_tokens(tokens)}


def remove_repeated_lines(page_texts: List[str], min_pages: int = 4, max_length: int = 90) -> List[str]:
    """Drop running headers/footers/page numbers that repeat on most pages (cleaned text only)."""
    if len(page_texts) < min_pages:
        return page_texts

    def norm(line: str) -> str:
        return re.sub(r"\d+", "#", line.strip().lower())

    counts: Dict[str, int] = {}
    for text in page_texts:
        edge = text.split("\n")
        candidates = set(norm(line) for line in edge[:3] + edge[-3:] if 0 < len(line) <= max_length)
        for key in candidates:
            counts[key] = counts.get(key, 0) + 1
    threshold = max(3, int(len(page_texts) * 0.6))
    boilerplate = {key for key, count in counts.items() if count >= threshold}
    if not boilerplate:
        return page_texts
    result = []
    for text in page_texts:
        lines = text.split("\n")
        kept = [line for index, line in enumerate(lines) if not ((index < 3 or index >= len(lines) - 3) and norm(line) in boilerplate)]
        result.append("\n".join(kept))
    return result
=======
=======
>>>>>>> origin/main
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
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm", disable=["ner", "tagger", "lemmatizer"])
        return [sentence.text.strip() for sentence in nlp(cleaned).sents if sentence.text.strip()]
    except Exception:
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", cleaned) if part.strip()]


def tokenize_text(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*'?", text)


def lemmatize_tokens(tokens: List[str]) -> List[str]:
    """Apply a deterministic lightweight lemmatization fallback.

    A trained lemmatizer can replace this function later without changing the
    pipeline contract.
    """
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        return [token.lemma_.lower() for token in nlp(" ".join(tokens)) if token.lemma_]
    except Exception:
        pass
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
<<<<<<< HEAD
>>>>>>> origin/main
=======
>>>>>>> origin/main
