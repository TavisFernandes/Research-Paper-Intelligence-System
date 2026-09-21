"""Scientific entity extraction with spaCy enhancement and deterministic patterns."""
import re
from collections import defaultdict

_PATTERNS = {
    "DATASET": r"\b(?:[A-Z][A-Za-z0-9-]+(?:[- ][A-Z][A-Za-z0-9-]+)*|ImageNet|MNIST|CIFAR-?10|SQuAD|GLUE|PubMedQA)\b",
    "METRIC": r"\b(?:accuracy|precision|recall|F1(?:-score)?|BLEU|ROUGE(?:-[12L])?|AUC|MRR|nDCG)\b",
    "MODEL": r"\b(?:BERT|RoBERTa|GPT(?:-[0-9.]+)?|T5|LED|Longformer|Transformer|LSTM|CNN|BGE-M3|Qwen)\b",
    "ALGORITHM": r"\b(?:attention|fine-?tuning|contrastive learning|retrieval|clustering|classification)\b",
}


def extract_entities(text: str) -> list[dict[str, str]]:
    found: dict[tuple[str, str], None] = {}
    for label, pattern in _PATTERNS.items():
        for match in re.finditer(pattern, text, re.I):
            value = match.group(0).strip()
            if len(value) > 2:
                found[(label, value)] = None
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        for entity in nlp(text[:200_000]).ents:
            if entity.label_ in {"ORG", "PERSON", "GPE", "DATE"}:
                found[(entity.label_, entity.text)] = None
    except Exception:
        pass
    return [{"label": label, "text": value} for label, value in found]
