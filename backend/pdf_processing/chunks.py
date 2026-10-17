<<<<<<< HEAD
<<<<<<< HEAD
"""Sentence-aware hierarchical chunking: paper -> page -> section -> chunk."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from .preprocess import segment_sentence_spans


def _page_for_offset(spans: List[Dict[str, int]], offset: int, fallback: int) -> int:
    for span in spans:
        if span["start"] <= offset <= span["end"]:
            return int(span["page"])
    # offset falls on a newline separator between spans: use the next span's page
    for span in spans:
        if span["start"] > offset:
            return int(span["page"])
    return fallback


def _split_long(text: str, start: int, limit: int) -> List[Tuple[int, int]]:
    """Split an over-long sentence at word boundaries into pieces of at most ``limit`` chars."""
    pieces: List[Tuple[int, int]] = []
    cursor, end = start, start + len(text)
    while end - cursor > limit:
        cut = text.rfind(" ", cursor - start, cursor - start + limit)
        cut = start + cut if cut > cursor - start else cursor + limit
        pieces.append((cursor, cut))
        cursor = cut + 1 if cut < end and text[cut - start:cut - start + 1] == " " else cut
    if cursor < end:
        pieces.append((cursor, end))
    return pieces


def _group_units(units: List[Tuple[int, int]], flat: str, chunk_size: int, overlap: int) -> List[List[Tuple[int, int]]]:
    """Pack sentence spans into groups of <= chunk_size chars, carrying a sentence-level overlap between groups."""
    def size(items: List[Tuple[int, int]]) -> int:
        return sum(e - s + 1 for s, e in items)

    groups: List[List[Tuple[int, int]]] = []
    current: List[Tuple[int, int]] = []
    has_new = False
    for unit in units:
        unit_len = unit[1] - unit[0] + 1
        if current and has_new and size(current) + unit_len > chunk_size:
            groups.append(list(current))
            carry: List[Tuple[int, int]] = []
            for previous in reversed(current):
                if size(carry) + (previous[1] - previous[0] + 1) <= overlap:
                    carry.insert(0, previous)
                else:
                    break
            if not carry and overlap:  # one long sentence: carry its tail words instead
                last_s, last_e = current[-1]
                boundary = flat.find(" ", max(last_s, last_e - overlap), last_e)
                if 0 <= boundary < last_e - 1:
                    carry = [(boundary + 1, last_e)]
            current = carry if size(carry) + unit_len <= chunk_size else []
            has_new = False
        current.append(unit)
        has_new = True
    if current and has_new:
        groups.append(current)
    return groups


def _build_chunk(section: Dict[str, object], section_index: int, current: List[Tuple[int, int]], body: str,
                 number: int, ordinal: int, spans: List[Dict[str, int]]) -> Dict[str, object]:
    name, paper_id = str(section["section_name"]), str(section["paper_id"])
    fallback_page = int(section["page_start"])  # type: ignore[arg-type]
    return {
        "paper_id": paper_id, "chunk_id": f"{paper_id}_{name}_{number:03d}", "section_name": name, "heading": section.get("heading"),
        "page_start": _page_for_offset(spans, current[0][0], fallback_page),
        "page_end": _page_for_offset(spans, max(current[-1][1] - 1, current[0][0]), fallback_page),
        "text": body, "chunk_index": ordinal, "section_index": section_index, "char_count": len(body),
    }


def create_chunks(sections: List[Dict[str, object]], chunk_size: int = 1200, overlap: int = 150,
                  include_references: bool = True) -> List[Dict[str, object]]:
    """Create overlapping, sentence-aligned chunks that keep paper/page/section provenance.

    ``chunk_size`` and ``overlap`` are in characters. Overlap is made of whole trailing
    sentences (or, when a single sentence is longer than the overlap, its tail words), so
    nothing is lost at boundaries. Chunk ids are deterministic:
    ``{paper_id}_{SECTION}_{NNN}`` with NNN counting per section name across the paper.
    """
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be smaller than chunk_size")
    chunks: List[Dict[str, object]] = []
    counters: Dict[str, int] = defaultdict(int)
    ordinal = 0
    for section_index, section in enumerate(sections):
        name = str(section["section_name"])
        if name == "REFERENCES" and not include_references:
            continue
        text = str(section["text"])
        flat = text.replace("\n", " ")
        spans = section.get("page_spans") or [{"page": section["page_start"], "start": 0, "end": len(text)}]

        units: List[Tuple[int, int]] = []
        for start, end in segment_sentence_spans(text) or [(0, len(flat))]:
            sentence = flat[start:end]
            if len(sentence) > chunk_size:
                units.extend(_split_long(sentence, start, chunk_size))
            else:
                units.append((start, end))

        for group in _group_units(units, flat, chunk_size, overlap):
            body = " ".join(flat[s:e].strip() for s, e in group).strip()
            if not body:
                continue
            counters[name] += 1
            ordinal += 1
            chunks.append(_build_chunk(section, section_index, group, body, counters[name], ordinal, spans))
=======
=======
>>>>>>> origin/main
from typing import Dict, List
from .preprocess import segment_sentences


def create_chunks(sections: List[Dict[str, object]], chunk_size: int = 1200, overlap: int = 150) -> List[Dict[str, object]]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be smaller than chunk_size")
    chunks: List[Dict[str, object]] = []
    for section in sections:
        text = str(section["text"])
        index = 1
        sentences = segment_sentences(text) or [text]
        current: List[str] = []
        current_len = 0
        for sentence in sentences:
            if current and current_len + len(sentence) + 1 > chunk_size:
                chunk_text = " ".join(current).strip()
                chunks.append({
                    "paper_id": section["paper_id"], "chunk_id": f"{section['paper_id']}_{section['section_name']}_{index:03d}",
                    "section_name": section["section_name"], "page_start": section["page_start"], "page_end": section["page_end"], "text": chunk_text,
                })
                index += 1
                overlap_text = chunk_text[-overlap:] if overlap else ""
                current = [overlap_text] if overlap_text else []
                current_len = len(overlap_text)
            current.append(sentence)
            current_len += len(sentence) + 1
        if current:
            chunk_text = " ".join(current).strip()
            if chunk_text:
                chunks.append({
                    "paper_id": section["paper_id"],
                    "chunk_id": f"{section['paper_id']}_{section['section_name']}_{index:03d}",
                    "section_name": section["section_name"],
                    "page_start": section["page_start"],
                    "page_end": section["page_end"],
                    "text": chunk_text,
                })
<<<<<<< HEAD
>>>>>>> origin/main
=======
>>>>>>> origin/main
    return chunks
