<<<<<<< HEAD
"""Scientific entity extraction.

Sources, reported on every entity as ``source``:
* ``scispacy``  - a SciSpaCy model (``en_core_sci_sm`` / ``en_core_sci_md``) when installed.
* ``spacy``     - ``en_core_web_sm`` for organisations when installed.
* ``rule``      - conservative gazetteer and cue-phrase rules for datasets, models,
                  algorithms and metrics ("trained on X", "X dataset", "evaluated with F1").

Nothing is fabricated: a label is only produced when a rule or model produced it.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from functools import lru_cache
from typing import Dict, Iterable, List, Tuple

logger = logging.getLogger(__name__)

_SCISPACY_MODELS = ("en_core_sci_md", "en_core_sci_sm", "en_core_sci_lg")

_METRICS = (r"Recall@\d+|Precision@\d+|MRR@\d+|nDCG@\d+|accuracy|precision|recall|F1(?:[- ]?score)?|BLEU(?:-\d)?|ROUGE(?:-[12L]|L)?|METEOR|BERTScore|AUC(?:-ROC)?|AUROC|"
            r"MRR|nDCG|MAP|perplexity|RMSE|MAE|MSE|IoU|mAP|exact match|top-[15] accuracy|"
            r"sensitivity|specificity|Dice(?: coefficient| score)?|Pearson correlation|Spearman correlation|WER|CER")
_MODELS = (r"BERT|RoBERTa|DistilBERT|ALBERT|DeBERTa|SciBERT|BioBERT|PubMedBERT|XLM-R(?:oBERTa)?|GPT(?:-[0-9.]+[A-Za-z]*)?|ChatGPT|T5|FLAN-T5|BART|PEGASUS|"
           r"LED|Longformer|BigBird|Transformer|LSTM|BiLSTM|GRU|RNN|CNN|ResNet(?:-?\d+)?|VGG(?:-?\d+)?|U-Net|ViT|CLIP|BGE-M3|BGE|Qwen[0-9.]*(?:-[0-9A-Za-z.]+)?|"
           r"LLaMA(?:-?\d+)?|Llama(?:-?\d+)?|Mistral|Gemini|Claude|XGBoost|Random Forest|SVM|support vector machine|logistic regression|naive Bayes|"
           r"k-means|word2vec|GloVe|FastText|TF-IDF|BM25|DPR|ColBERT|YOLO(?:v?\d+)?|GAN|VAE|Mamba")
_ALGORITHMS = (r"attention|self-attention|fine-?tuning|contrastive learning|retrieval-augmented generation|RAG|clustering|gradient descent|SGD|Adam|AdamW|"
               r"backpropagation|dropout|beam search|reinforcement learning|transfer learning|cross-validation|data augmentation|pre-?training|"
               r"knowledge distillation|LoRA|in-batch negatives|hard negative mining|maximum likelihood|Monte Carlo")
_KNOWN_DATASETS = (r"ImageNet|MNIST|CIFAR-?(?:10|100)|COCO|SQuAD(?: ?2\.0)?|GLUE|SuperGLUE|PubMedQA|PubMed|arXiv|MS ?MARCO|BEIR|MIRACL|TriviaQA|"
                   r"Natural Questions|HotpotQA|CNN/DailyMail|XSum|WikiText(?:-\d+)?|Wikipedia|BookCorpus|Common Crawl|MIMIC-?(?:III|IV)|CheXpert|"
                   r"BioASQ|SciTLDR|S2ORC|CORD-19|MedQA|MMLU|GSM8K|HumanEval|OpenWebText|The Pile|LibriSpeech|Cityscapes|Pascal VOC|KITTI")

_COMPILED_RULES: List[Tuple[str, "re.Pattern[str]"]] = [
    ("METRIC", re.compile(rf"\b(?:{_METRICS})\b", re.I)),
    ("MODEL", re.compile(rf"\b(?:{_MODELS})\b")),
    ("ALGORITHM", re.compile(rf"\b(?:{_ALGORITHMS})\b", re.I)),
    ("DATASET", re.compile(rf"\b(?:{_KNOWN_DATASETS})\b")),
]
# "<Capitalised Name> dataset/corpus/benchmark" and "trained/evaluated/tested on the <Name>"
_DATASET_CUES = [
    re.compile(r"\b((?:[A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,3}))\s+(?:dataset|corpus|benchmark|data set)s?\b"),
    re.compile(r"\b(?:trained|fine-?tuned|evaluated|tested|validated|experiments? (?:were )?(?:conducted|performed|run))\s+(?:on|using|with)\s+(?:the\s+)?((?:[A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,3}))"),
]
_CUE_STOP = {"The", "This", "That", "These", "Our", "We", "A", "An", "In", "On", "For", "Each", "Both", "Such", "Training", "Test", "Validation", "Evaluation"}


@lru_cache(maxsize=1)
def _load_scispacy():
    try:
        import spacy
    except ImportError:
        return None, "scispacy unavailable: spaCy not installed"
    for model in _SCISPACY_MODELS:
        try:
            return spacy.load(model), f"scispacy:{model}"
        except OSError:
            continue
    return None, "scispacy unavailable: install a model, e.g. pip install scispacy and the en_core_sci_sm wheel"


@lru_cache(maxsize=1)
def _load_general():
    try:
        import spacy

        return spacy.load("en_core_web_sm", disable=["lemmatizer"]), "spacy:en_core_web_sm"
    except Exception:
        return None, "spacy en_core_web_sm unavailable (python -m spacy download en_core_web_sm)"


def ner_status() -> Dict[str, str]:
    return {"scispacy": _load_scispacy()[1], "spacy": _load_general()[1], "rules": "enabled"}


def _clean_candidate(value: str) -> str:
    words = value.split()
    while words and words[0] in _CUE_STOP:
        words.pop(0)
    return " ".join(words).strip(" ,.;:()")


def _rule_entities(text: str) -> Iterable[Tuple[str, str, str]]:
    for label, pattern in _COMPILED_RULES:
        for match in pattern.finditer(text):
            yield label, match.group(0), "rule"
    for pattern in _DATASET_CUES:
        for match in pattern.finditer(text):
            candidate = _clean_candidate(match.group(1))
            if len(candidate) >= 3 and candidate not in _CUE_STOP and not candidate.islower():
                yield "DATASET", candidate, "rule"


def extract_entities(text: str, max_chars: int = 200_000) -> List[Dict[str, object]]:
    """Return unique entities as ``{label, text, source, count}`` sorted by frequency."""
    text = text[:max_chars].replace("\n", " ")
    counter: Counter = Counter()
    rule_found = list(_rule_entities(text))
    for label, value, source in rule_found:
        key = value if label in {"MODEL", "DATASET"} else value.lower() if label == "ALGORITHM" else value
        counter[(label, key, source)] += 1
    scispacy, _ = _load_scispacy()
    if scispacy is not None:
        try:
            for ent in scispacy(text).ents:
                if len(ent.text) > 2:
                    counter[("SCIENTIFIC_ENTITY", ent.text.strip(), "scispacy")] += 1
        except Exception:
            logger.exception("SciSpaCy extraction failed")
    general, _ = _load_general()
    if general is not None:
        try:
            for ent in general(text).ents:
                if (ent.label_ == "ORG" and len(ent.text) > 2 and not ent.text.islower() and "@" not in ent.text
                        and len(ent.text.split()) <= 6 and not any(ent.text.lower() == v.lower() for _, v, _ in rule_found)):
                    counter[("ORGANIZATION", ent.text.strip(), "spacy")] += 1
        except Exception:
            logger.exception("spaCy NER failed")
    merged: Dict[Tuple[str, str], Dict[str, object]] = {}
    for (label, value, source), count in counter.items():
        key = (label, value.lower())
        if key in merged:
            merged[key]["count"] = int(merged[key]["count"]) + count  # type: ignore[arg-type]
        else:
            merged[key] = {"label": label, "text": value, "source": source, "count": count}
    return sorted(merged.values(), key=lambda e: (-int(e["count"]), str(e["label"]), str(e["text"])))  # type: ignore[arg-type]
=======
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
>>>>>>> origin/main
