"""Pairwise comparison and multi-paper insights.

Two kinds of content are always kept apart:
* ``reported``  - verbatim sentences / NER entities with section and page provenance.
* ``inferred``  - set overlaps and similarity scores *computed* from the reported data.
Optional LLM prose is labelled ``generated`` and is grounded only in the reported table.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from embeddings import get_embedder
from errors import InvalidInputError, LLMUnavailable
from llm import llm
from nlp import extract_keywords

from .extraction import DIMENSIONS, extract_dimension, extract_reported_results

logger = logging.getLogger(__name__)
NOT_REPORTED = "Not reported / not identified in the extracted text"
_KEY_SECTIONS = ("ABSTRACT", "INTRODUCTION", "CONCLUSION")


def _identity(paper: Dict[str, Any]) -> Dict[str, Any]:
    return {"paper_id": paper["paper_id"], "title": paper.get("title"), "filename": paper.get("filename")}


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    x, y = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(x) * np.linalg.norm(y))
    return float(x @ y / denom) if denom else 0.0


def _key_text(paper: Dict[str, Any], limit: int = 3000) -> str:
    parts = [str(s["text"]) for name in _KEY_SECTIONS for s in paper.get("sections", []) if s["section_name"] == name]
    text = " ".join(parts) or " ".join(str(c["text"]) for c in paper.get("chunks", [])[:6])
    return text[:limit]


def _similarity_basis() -> str:
    embedder = get_embedder()
    return "semantic embedding cosine similarity" if embedder.is_semantic else "lexical hashing cosine (non-semantic fallback embeddings)"


def _cell(dimension: Dict[str, Any]) -> Dict[str, Any]:
    if dimension["status"] != "found":
        return {"text": NOT_REPORTED, "sources": [], "entities": []}
    text = " ".join(e["text"] for e in dimension["evidence"]) or ", ".join(dimension["entities"])
    sources = [{"section_name": e["section_name"], "page_start": e["page_start"], "page_end": e["page_end"], "chunk_id": e["chunk_id"]}
               for e in dimension["evidence"]]
    return {"text": text, "sources": sources, "entities": dimension["entities"]}


def compare_papers(left: Dict[str, Any], right: Dict[str, Any], use_llm: bool = False) -> Dict[str, Any]:
    """Structured comparison across the ATML dimensions with provenance and computed overlaps."""
    if left["paper_id"] == right["paper_id"]:
        raise InvalidInputError("Select two different papers to compare.")
    embedder = get_embedder()
    dimensions: List[Dict[str, Any]] = []
    table: List[Dict[str, Any]] = []
    similarities: List[str] = []
    differences: List[str] = []
    for spec in DIMENSIONS:
        l_dim, r_dim = extract_dimension(left, spec["key"]), extract_dimension(right, spec["key"])
        l_cell, r_cell = _cell(l_dim), _cell(r_dim)
        similarity: Optional[float] = None
        if l_dim["status"] == "found" and r_dim["status"] == "found":
            vectors = embedder.encode([l_cell["text"], r_cell["text"]])
            similarity = round(_cosine(vectors[0], vectors[1]), 3)  # type: ignore[arg-type,index]
        l_set = {e.lower(): e for e in l_dim["entities"]}
        r_set = {e.lower(): e for e in r_dim["entities"]}
        shared = sorted(l_set[k] for k in l_set.keys() & r_set.keys())
        only_l = sorted(l_set[k] for k in l_set.keys() - r_set.keys())
        only_r = sorted(r_set[k] for k in r_set.keys() - l_set.keys())
        if shared:
            similarities.append(f"{spec['label']}: both papers mention {', '.join(shared)}.")
        if only_l or only_r:
            differences.append(f"{spec['label']}: only paper {left['paper_id']} mentions {', '.join(only_l) or '—'}; "
                               f"only paper {right['paper_id']} mentions {', '.join(only_r) or '—'}.")
        if l_dim["status"] != r_dim["status"]:
            missing = right["paper_id"] if l_dim["status"] == "found" else left["paper_id"]
            differences.append(f"{spec['label']}: not reported/identified in paper {missing}.")
        dimensions.append({"key": spec["key"], "label": spec["label"], "left": l_dim, "right": r_dim, "similarity": similarity,
                           "entity_overlap": {"shared": shared, "only_left": only_l, "only_right": only_r,
                                              "type": "inferred", "basis": "case-insensitive overlap of NER entities"}})
        table.append({"dimension": spec["label"], "left": l_cell, "right": r_cell})
    vectors = embedder.encode([_key_text(left), _key_text(right)])
    overall = round(_cosine(vectors[0], vectors[1]), 3)  # type: ignore[arg-type,index]
    result: Dict[str, Any] = {
        "left": _identity(left), "right": _identity(right),
        "left_paper_id": left["paper_id"], "right_paper_id": right["paper_id"],
        "overall_similarity": overall, "similarity_basis": _similarity_basis(),
        "dimensions": dimensions, "table": table,
        "reported_results": {left["paper_id"]: extract_reported_results(left), right["paper_id"]: extract_reported_results(right)},
        "inferred": {"similarities": similarities, "differences": differences,
                     "note": "Computed from the reported evidence (entity overlap / missing sections); not statements made by the papers."},
        "provenance": {"reported": "Sentences and entities are copied from the papers with section and page numbers.",
                       "inferred": "Overlaps and similarity scores are computed by this system.",
                       "limits": "Dimension extraction is rule-based: absent text means 'not identified', not 'absent from the paper'."},
        "narrative": None,
    }
    if use_llm:
        result["narrative"] = _narrative(result)
    return result


def _narrative(comparison: Dict[str, Any]) -> Dict[str, Any]:
    if not llm.configured:
        return {"status": "unavailable", "generated": False, "message": "No language model is configured."}
    rows = []
    for row in comparison["table"]:
        rows.append(f"## {row['dimension']}\nPaper {comparison['left_paper_id']}: {row['left']['text']}\nPaper {comparison['right_paper_id']}: {row['right']['text']}")
    prompt = ("Using ONLY the extracted evidence below, write a short comparison of the two papers. "
              "State when a dimension is not reported. Do not add numbers or claims that are not in the evidence.\n\n" + "\n\n".join(rows))
    try:
        text = llm.chat([{"role": "system", "content": "You compare research papers strictly from supplied evidence."}, {"role": "user", "content": prompt}])
        return {"status": "ok", "generated": True, "text": text, "model": llm.info()["model"]}
    except LLMUnavailable as exc:
        return {"status": "unavailable", "generated": False, "message": exc.public_message}


def _group(papers: Sequence[Dict[str, Any]], labels: Sequence[str]) -> List[Dict[str, Any]]:
    """Entities (of the given labels) with the papers that mention them; common = in >= 2 papers."""
    holders: Dict[str, set] = defaultdict(set)
    display: Dict[str, str] = {}
    for paper in papers:
        for entity in paper.get("analysis", {}).get("entities", []):
            if entity["label"] in labels:
                key = str(entity["text"]).lower()
                holders[key].add(paper["paper_id"])
                display.setdefault(key, str(entity["text"]))
    rows = [{"name": display[k], "papers": sorted(v), "count": len(v), "common": len(v) >= 2} for k, v in holders.items()]
    return sorted(rows, key=lambda r: (-r["count"], r["name"].lower()))


def _shared_terms(texts: Dict[str, str], top: int = 8) -> List[Dict[str, Any]]:
    holders: Dict[str, set] = defaultdict(set)
    for pid, text in texts.items():
        if text.strip():
            for item in extract_keywords(text, limit=15):
                if " " not in str(item["keyword"]):
                    holders[str(item["keyword"])].add(pid)
    rows = [{"term": t, "papers": sorted(p), "count": len(p)} for t, p in holders.items() if len(p) >= 2]
    return sorted(rows, key=lambda r: (-r["count"], r["term"]))[:top]


def research_insights(papers: Sequence[Dict[str, Any]], use_llm: bool = False) -> Dict[str, Any]:
    """Collection-level insights across >= 2 papers (reported vs inferred are labelled)."""
    if len(papers) < 2:
        raise InvalidInputError("Select at least two papers for multi-paper insights.")
    embedder = get_embedder()
    vectors = embedder.encode([_key_text(p) for p in papers])
    ids = [p["paper_id"] for p in papers]
    matrix = [[round(_cosine(a, b), 3) for b in vectors] for a in vectors]  # type: ignore[union-attr]
    dims = {p["paper_id"]: {d["key"]: extract_dimension(p, d["key"]) for d in DIMENSIONS} for p in papers}

    def texts(key: str) -> Dict[str, str]:
        return {pid: " ".join(e["text"] for e in dims[pid][key]["evidence"]) for pid in ids}

    def reported(key: str) -> List[Dict[str, Any]]:
        return [{"paper_id": pid, "type": "reported", "evidence": dims[pid][key]["evidence"]} for pid in ids if dims[pid][key]["evidence"]]

    results = {p["paper_id"]: extract_reported_results(p) for p in papers}
    by_metric: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for pid, pairs in results.items():
        for pair in pairs:
            by_metric[pair["metric"].lower()].append({"paper_id": pid, "value": pair["value"], "sentence": pair["sentence"], "section_name": pair["section_name"], "page": pair["page"]})
    performance = [{"metric": m, "reports": rows, "papers": sorted({r["paper_id"] for r in rows}),
                    "note": "Values are copied from the papers; they are comparable only when dataset and protocol match."}
                   for m, rows in sorted(by_metric.items(), key=lambda kv: -len(kv[1]))]

    datasets, metrics = _group(papers, ["DATASET"]), _group(papers, ["METRIC"])
    gaps_inferred = []
    for row in datasets:
        if not row["common"]:
            gaps_inferred.append({"type": "inferred", "text": f"Dataset '{row['name']}' is mentioned only in paper {row['papers'][0]}; "
                                  "it is not mentioned in the other selected papers."})
    for row in metrics:
        if not row["common"]:
            gaps_inferred.append({"type": "inferred", "text": f"Metric '{row['name']}' is mentioned only in paper {row['papers'][0]}."})

    insights: Dict[str, Any] = {
        "paper_count": len(papers), "papers": [_identity(p) for p in papers],
        "similarity_matrix": {"paper_ids": ids, "values": matrix, "basis": _similarity_basis(), "type": "inferred",
                              "text_used": "abstract + introduction + conclusion (first 3000 characters)"},
        "common_methodologies": {"type": "inferred", "basis": "terms shared by the methodology evidence of >= 2 papers", "terms": _shared_terms(texts("methodology")),
                                 "reported": reported("methodology")},
        "common_datasets": datasets, "common_models": _group(papers, ["MODEL"]), "common_algorithms": _group(papers, ["ALGORITHM"]),
        "common_metrics": metrics,
        "performance_patterns": {"type": "reported", "metrics": performance[:12]},
        "recurring_problems": {"type": "inferred", "shared_terms": _shared_terms(texts("research_problem")), "reported": reported("research_problem")},
        "common_limitations": {"type": "inferred", "shared_terms": _shared_terms(texts("limitations")), "reported": reported("limitations")},
        "recurring_themes": {"type": "inferred", "basis": "keywords occurring in >= 2 papers",
                             "terms": _shared_terms({p["paper_id"]: " ".join(str(c["text"]) for c in p.get("chunks", [])) for p in papers}, top=10),
                             "note": "Publication years are not extracted, so no temporal trend is claimed."},
        "research_gaps": {"reported_future_work": reported("future_work"), "reported_limitations": reported("limitations"), "inferred": gaps_inferred[:10],
                          "note": "Reported items are the papers' own statements. Inferred items only describe differences within the selected papers, not gaps in the wider literature."},
        "caveats": ["Dimension extraction is rule-based; 'not reported' means no matching text was identified.",
                    "Similarity values are computed by this system and are not claims made by the papers."],
        "narrative": None,
    }
    if use_llm:
        insights["narrative"] = _insights_narrative(insights)
    return insights


def _insights_narrative(insights: Dict[str, Any]) -> Dict[str, Any]:
    if not llm.configured:
        return {"status": "unavailable", "generated": False, "message": "No language model is configured."}
    import json

    compact = {k: insights[k] for k in ("common_datasets", "common_models", "common_metrics", "performance_patterns", "research_gaps")}
    try:
        text = llm.chat([{"role": "system", "content": "You summarise multi-paper findings strictly from supplied JSON evidence. Never invent numbers or gaps."},
                         {"role": "user", "content": "Summarise the cross-paper insights from this evidence only:\n" + json.dumps(compact)[:12000]}])
        return {"status": "ok", "generated": True, "text": text}
    except LLMUnavailable as exc:
        return {"status": "unavailable", "generated": False, "message": exc.public_message}
