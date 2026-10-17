<<<<<<< HEAD
"""Rule-based scientific section detection with page-level provenance.

Only headings that can be identified reliably are used. Text before the first
recognised heading is labelled ``UNKNOWN`` rather than guessed. Unrecognised numbered
headings (e.g. ``3.1 Training details``) are kept as *subsections* of the current
section so the hierarchy is preserved without inventing section boundaries.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

SECTION_ALIASES: Dict[str, set] = {
    "ABSTRACT": {"abstract", "summary", "executive summary"},
    "INTRODUCTION": {"introduction", "background", "background and motivation", "motivation", "overview"},
    "RELATED_WORK": {"related work", "related works", "literature review", "prior work", "previous work", "background and related work", "related studies"},
    "METHODOLOGY": {"methodology", "methods", "method", "approach", "materials and methods", "methods and materials", "proposed method", "proposed approach", "proposed methodology", "model", "our approach", "method overview", "framework", "proposed framework"},
    "DATASET": {"dataset", "datasets", "data", "corpus", "data collection", "data and preprocessing", "dataset description"},
    "EXPERIMENTS": {"experiments", "experiment", "experimental setup", "experimental results", "experiments and results", "evaluation", "experimental evaluation", "implementation details", "experimental design"},
    "RESULTS": {"results", "findings", "results and analysis", "main results", "empirical results"},
    "DISCUSSION": {"discussion", "analysis", "results and discussion", "discussion and conclusion", "discussion and conclusions"},
    "LIMITATIONS": {"limitations", "limitation", "limitations and future work", "threats to validity"},
    "CONCLUSION": {"conclusion", "conclusions", "concluding remarks", "summary and conclusion", "conclusion and future work", "conclusions and future work"},
    "FUTURE_WORK": {"future work", "future directions", "future research", "future research directions", "outlook"},
    "ACKNOWLEDGMENTS": {"acknowledgments", "acknowledgements", "acknowledgment", "acknowledgement"},
    "REFERENCES": {"references", "bibliography", "works cited", "literature cited"},
    "APPENDIX": {"appendix", "appendices", "supplementary material", "supplementary materials", "supplemental material"},
}

# Containment rules, used only for numbered or ALL-CAPS short headings (never for prose lines).
_KEYWORD_RULES: List[Tuple[str, str]] = [
    ("related work", "RELATED_WORK"), ("literature", "RELATED_WORK"), ("background", "INTRODUCTION"),
    ("introduction", "INTRODUCTION"), ("future work", "FUTURE_WORK"), ("future research", "FUTURE_WORK"),
    ("limitation", "LIMITATIONS"), ("conclusion", "CONCLUSION"), ("discussion", "DISCUSSION"),
    ("result", "RESULTS"), ("experiment", "EXPERIMENTS"), ("dataset", "DATASET"), ("method", "METHODOLOGY"),
    ("approach", "METHODOLOGY"), ("acknowledg", "ACKNOWLEDGMENTS"), ("reference", "REFERENCES"), ("appendix", "APPENDIX"),
]

_NUMBER_RE = re.compile(r"^\s*(?:(?P<arabic>\d+(?:\.\d+)*)\.?|(?P<roman>[IVX]{1,6})\.|(?P<letter>[A-Z])\.)\s+(?P<rest>\S.*)$")
_INLINE_ABSTRACT_RE = re.compile(r"^\s*abstract\s*[\u2014\u2013:.\-]+\s*(?P<body>\S.*)$", re.I)


def _normalise(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip().rstrip(":").strip()
    if re.fullmatch(r"(?:[A-Za-z] ){3,}[A-Za-z]", text):  # "A B S T R A C T"
        text = text.replace(" ", "")
    return text.lower()


def _match_alias(normalised: str, numbered_or_caps: bool) -> Optional[str]:
    for section, aliases in SECTION_ALIASES.items():
        if normalised in aliases:
            return section
    if numbered_or_caps:
        for keyword, section in _KEYWORD_RULES:
            if keyword in normalised and len(normalised.split()) <= 6:
                return section
    return None


def classify_heading(line: str, last_top_number: Optional[int] = None) -> Optional[Dict[str, object]]:
    """Classify one text line. Returns heading info or ``None`` when it is body text.

    The result has keys: ``section`` (canonical name or ``None`` for an unrecognised
    numbered heading), ``heading`` (display text), ``level`` (1 or 2+), ``number``.
    """
    stripped = line.strip()
    if re.fullmatch(r"(?:[A-Za-z] ){3,}[A-Za-z]", stripped):  # letter-spaced heading "A B S T R A C T"
        stripped = stripped.replace(" ", "")
    if not stripped or len(stripped) > 90:
        return None
    number_match = _NUMBER_RE.match(stripped)
    number: Optional[str] = None
    body = stripped
    level = 1
    if number_match:
        body = number_match.group("rest").strip()
        number = number_match.group("arabic") or number_match.group("roman") or number_match.group("letter")
        level = number.count(".") + 1 if number_match.group("arabic") else 1
    if body.endswith(".") or not re.search(r"[A-Za-z]{3}", body):
        return None
    letters = sum(c.isalpha() for c in body)
    if letters < 0.6 * len(body):
        return None
    caps = body.isupper() and len(body.split()) <= 6
    section = _match_alias(_normalise(body), numbered_or_caps=bool(number) or caps)
    if section:
        return {"section": section, "heading": body.rstrip(":"), "level": level, "number": number}
    # Unrecognised heading: accept only when numbering makes it reliable.
    if number_match and number_match.group("arabic") and len(body.split()) <= 9 and body[0].isupper():
        if level >= 2:
            return {"section": None, "heading": body.rstrip(":"), "level": level, "number": number}
        if last_top_number is not None and int(number) == last_top_number + 1 and not re.search(r"[,;]$", body):
            return {"section": "OTHER", "heading": body.rstrip(":"), "level": 1, "number": number}
=======
import re
from typing import Dict, List, Optional

SECTION_ALIASES = {
    "ABSTRACT": {"abstract", "summary"},
    "INTRODUCTION": {"introduction", "background"},
    "RELATED_WORK": {"related work", "related works", "literature review", "prior work"},
    "METHODOLOGY": {"methodology", "methods", "method", "approach", "materials and methods"},
    "DATASET": {"dataset", "data", "corpus"},
    "EXPERIMENTS": {"experiments", "experimental setup", "experimental results"},
    "RESULTS": {"results", "findings"},
    "DISCUSSION": {"discussion", "analysis"},
    "LIMITATIONS": {"limitations", "limitation"},
    "CONCLUSION": {"conclusion", "conclusions"},
    "FUTURE_WORK": {"future work", "future directions"},
    "REFERENCES": {"references", "bibliography"},
}


def _heading_name(line: str) -> Optional[str]:
    normalized = re.sub(r"^\s*(?:\d+(?:\.\d+)*[.)]?\s*)", "", line).strip().rstrip(":")
    normalized = re.sub(r"\s+", " ", normalized).lower()
    if len(normalized) > 80 or not normalized or normalized.endswith("."):
        return None
    for section, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return section
>>>>>>> origin/main
    return None


def detect_sections(pages: List[Dict[str, object]], paper_id: str) -> List[Dict[str, object]]:
<<<<<<< HEAD
    """Group page text into sections. Every section keeps page provenance.

    Each section has: paper_id, section_name, heading, level, page_start, page_end, text,
    page_spans ([{page, start, end}] offsets into ``text``) and subsections.
    """
    sections: List[Dict[str, object]] = []
    state: Dict[str, object] = {"name": "UNKNOWN", "heading": None, "start": None, "lines": [], "subs": []}
    last_top_number: List[Optional[int]] = [None]

    def flush() -> None:
        lines: List[Tuple[int, str]] = state["lines"]  # type: ignore[assignment]
        if not lines:
            return
        text_parts: List[str] = []
        spans: List[Dict[str, int]] = []
        cursor = 0
        for page_number, line in lines:
            if text_parts:
                cursor += 1  # newline separator
            start = cursor
            cursor += len(line)
            text_parts.append(line)
            if spans and spans[-1]["page"] == page_number:
                spans[-1]["end"] = cursor
            else:
                spans.append({"page": page_number, "start": start, "end": cursor})
        text = "\n".join(text_parts)
        if not text.strip():
            return
        sections.append({
            "paper_id": paper_id, "section_name": state["name"], "heading": state["heading"], "level": 1,
            "page_start": spans[0]["page"], "page_end": spans[-1]["page"], "text": text,
            "page_spans": spans, "subsections": list(state["subs"]),
        })

    def start_section(name: str, heading: str, page_number: int) -> None:
        flush()
        state.update({"name": name, "heading": heading, "start": page_number, "lines": [], "subs": []})

    for page in pages:
        page_number = int(page["page_number"])  # type: ignore[arg-type]
        for line in str(page.get("cleaned_text", "")).splitlines():
            inline = _INLINE_ABSTRACT_RE.match(line)
            if inline:
                start_section("ABSTRACT", "Abstract", page_number)
                state["lines"].append((page_number, inline.group("body")))  # type: ignore[union-attr]
                continue
            heading = classify_heading(line, last_top_number[0])
            if heading is None:
                state["lines"].append((page_number, line))  # type: ignore[union-attr]
                continue
            if heading["level"] == 1 and heading["number"] and str(heading["number"]).isdigit():
                last_top_number[0] = int(str(heading["number"]))
            if heading["section"] is None:  # numbered subsection of the current section
                state["subs"].append({"heading": heading["heading"], "level": heading["level"], "page_number": page_number,  # type: ignore[union-attr]
                                      "char_offset": sum(len(l) + 1 for _, l in state["lines"])})  # type: ignore[union-attr]
                state["lines"].append((page_number, line))  # type: ignore[union-attr]
                continue
            if heading["level"] >= 2 and heading["section"] == state["name"]:
                # e.g. "3.1 Methods" directly under "3 Methods": stay in the same section.
                state["lines"].append((page_number, line))  # type: ignore[union-attr]
                continue
            start_section(str(heading["section"]), str(heading["heading"]), page_number)
    flush()
=======
    sections: List[Dict[str, object]] = []
    current_name = "UNKNOWN"
    current_start = 1
    current_parts: List[str] = []

    def flush(end_page: int) -> None:
        if not current_parts:
            return
        text = " ".join(part.strip() for part in current_parts if part.strip()).strip()
        if text:
            sections.append({"paper_id": paper_id, "section_name": current_name, "page_start": current_start, "page_end": end_page, "text": text})

    for page in pages:
        page_number = int(page["page_number"])
        for line in str(page.get("cleaned_text", "")).splitlines():
            heading = _heading_name(line)
            if heading:
                flush(page_number)
                current_name = heading
                current_start = page_number
                current_parts = []
            else:
                current_parts.append(line)
    flush(int(pages[-1]["page_number"]) if pages else 1)
>>>>>>> origin/main
    return sections
