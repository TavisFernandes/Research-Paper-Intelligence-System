"""Evidence-grounded extraction of research dimensions from a processed paper.

Everything returned here is *reported text* (verbatim sentences with section/page provenance)
or entities found by NER. Nothing is generated. A dimension with no supporting sentence is
reported as ``not_reported`` instead of being guessed.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pdf_processing.preprocess import segment_sentence_spans

DIMENSIONS: List[Dict[str, Any]] = [
    {"key": "research_problem", "label": "Research problem", "sections": ["ABSTRACT", "INTRODUCTION"],
     "cue": r"\b(problem|challenge|gap|address|issue|lack|difficult|limited|motivat|remains|bottleneck|we study|investigate)", "dedicated": []},
    {"key": "objectives", "label": "Objectives", "sections": ["ABSTRACT", "INTRODUCTION"],
     "cue": r"\b(we (propose|present|introduce|aim|develop|investigate|study|evaluate|seek)|objective|goal|aims? (to|of)|this (paper|work|study|article))", "dedicated": []},
    {"key": "methodology", "label": "Methodology", "sections": ["METHODOLOGY", "EXPERIMENTS", "ABSTRACT"],
     "cue": r"\b(we (use|used|train|trained|fine-?tune|implement|apply|employ|design|build|adopt)|method|approach|architecture|pipeline|framework|algorithm)", "dedicated": ["METHODOLOGY"]},
    {"key": "datasets", "label": "Datasets", "sections": ["DATASET", "METHODOLOGY", "EXPERIMENTS", "ABSTRACT"],
     "cue": r"\b(dataset|data set|corpus|benchmark|trained on|evaluated on|collected|samples|annotated)", "dedicated": ["DATASET"], "entities": ["DATASET"]},
    {"key": "models_algorithms", "label": "Models / algorithms", "sections": ["METHODOLOGY", "EXPERIMENTS", "ABSTRACT"],
     "cue": r"\b(model|network|classifier|encoder|decoder|transformer|algorithm|baseline|architecture)", "dedicated": [], "entities": ["MODEL", "ALGORITHM"]},
    {"key": "metrics", "label": "Evaluation metrics", "sections": ["EXPERIMENTS", "RESULTS", "METHODOLOGY", "ABSTRACT"],
     "cue": r"\b(metric|evaluat|measured|measure|score|accuracy|precision|recall|f1|rouge|bleu|auc|ndcg|mrr)", "dedicated": [], "entities": ["METRIC"]},
    {"key": "results", "label": "Results", "sections": ["RESULTS", "EXPERIMENTS", "ABSTRACT"],
     "cue": r"(\d+(\.\d+)?\s?%|\b\d+\.\d+\b)", "dedicated": [], "numeric": True},
    {"key": "findings", "label": "Findings", "sections": ["RESULTS", "DISCUSSION", "CONCLUSION", "ABSTRACT"],
     "cue": r"\b(we (find|found|show|observe|demonstrate|conclude)|results? (show|indicate|suggest|demonstrate)|reveal|outperform|improv|conclude)", "dedicated": []},
    {"key": "limitations", "label": "Limitations", "sections": ["LIMITATIONS", "DISCUSSION", "CONCLUSION"],
     "cue": r"\b(limit|however|only|restricted|cannot|fail|constraint|weakness|shortcoming|does not|did not|not able)", "dedicated": ["LIMITATIONS"]},
    {"key": "future_work", "label": "Future work", "sections": ["FUTURE_WORK", "CONCLUSION", "LIMITATIONS", "DISCUSSION"],
     "cue": r"\b(future|plan to|will explore|will investigate|extend|further (research|work|study)|next step|could be|remains to)", "dedicated": ["FUTURE_WORK"]},
]
DIM_BY_KEY = {d["key"]: d for d in DIMENSIONS}
_METRIC_VALUE = re.compile(
    r"(?P<metric>Recall@\d+|Precision@\d+|MRR@\d+|nDCG@\d+|ROUGE-?[12L]|ROUGE|BLEU|F1(?:[- ]?score)?|accuracy|precision|recall|AUC|AUROC|perplexity|RMSE|MAE|mAP|IoU|exact match)"
    r"[^0-9\n]{0,30}?(?P<value>\d+(?:\.\d+)?\s?%?)", re.I)


def _page_at(section: Dict[str, Any], offset: int) -> int:
    for span in section.get("page_spans") or []:
        if span["start"] <= offset <= span["end"]:
            return int(span["page"])
    return int(section["page_start"])


def _section_sentences(section: Dict[str, Any]) -> List[Dict[str, Any]]:
    text = str(section["text"])
    flat = text.replace("\n", " ")
    out = []
    for start, end in segment_sentence_spans(text):
        sentence = flat[start:end].strip()
        if len(sentence.split()) >= 4:
            out.append({"text": sentence, "section_name": section["section_name"], "page": _page_at(section, start),
                        "page_start": _page_at(section, start), "page_end": _page_at(section, max(end - 1, start))})
    return out


def _chunk_id_for(paper: Dict[str, Any], sentence: str, section_name: str) -> Optional[str]:
    probe = sentence[:60]
    for chunk in paper.get("chunks", []):
        if chunk.get("section_name") == section_name and probe in str(chunk.get("text", "")):
            return str(chunk["chunk_id"])
    return None


def extract_dimension(paper: Dict[str, Any], key: str, max_evidence: int = 4, max_chars: int = 420) -> Dict[str, Any]:
    """Return ``{status, evidence[], entities[]}`` for one dimension of one paper."""
    spec = DIM_BY_KEY[key]
    cue = re.compile(spec["cue"], re.I)
    sections = paper.get("sections", [])
    evidence: List[Dict[str, Any]] = []
    for name in spec["sections"]:
        for section in (s for s in sections if s["section_name"] == name):
            sentences = _section_sentences(section)
            matched = [s for s in sentences if cue.search(s["text"])]
            if name in spec.get("dedicated", []) and not matched:
                matched = sentences[:2]  # a dedicated section is relevant by definition
            for sentence in matched:
                if spec.get("numeric") and not re.search(r"\d", sentence["text"]):
                    continue
                if any(sentence["text"] == e["text"] for e in evidence):
                    continue
                text = sentence["text"] if len(sentence["text"]) <= max_chars else sentence["text"][:max_chars].rsplit(" ", 1)[0] + "…"
                evidence.append({"text": text, "section_name": name, "page_start": sentence["page_start"], "page_end": sentence["page_end"],
                                 "chunk_id": _chunk_id_for(paper, sentence["text"], name)})
                if len(evidence) >= max_evidence:
                    break
            if len(evidence) >= max_evidence:
                break
        if len(evidence) >= max_evidence:
            break
    labels = spec.get("entities", [])
    entities = [e["text"] for e in paper.get("analysis", {}).get("entities", []) if e["label"] in labels][:12]
    status = "found" if evidence or entities else "not_reported"
    return {"status": status, "evidence": evidence, "entities": entities}


def extract_reported_results(paper: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Metric/value pairs copied verbatim from results-like sections (no computation, no inference)."""
    pairs: List[Dict[str, Any]] = []
    seen = set()
    for name in ("RESULTS", "EXPERIMENTS", "ABSTRACT", "CONCLUSION"):
        for section in (s for s in paper.get("sections", []) if s["section_name"] == name):
            for sentence in _section_sentences(section):
                for match in _METRIC_VALUE.finditer(sentence["text"]):
                    key = (match.group("metric").lower(), match.group("value").strip(), sentence["text"])
                    if key in seen:
                        continue
                    seen.add(key)
                    pairs.append({"metric": match.group("metric"), "value": match.group("value").strip(), "sentence": sentence["text"][:300],
                                  "section_name": name, "page": sentence["page"]})
    return pairs[:30]
