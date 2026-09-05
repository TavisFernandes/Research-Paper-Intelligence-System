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
    return None


def detect_sections(pages: List[Dict[str, object]], paper_id: str) -> List[Dict[str, object]]:
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
    return sections
