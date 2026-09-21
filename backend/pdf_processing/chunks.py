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
    return chunks
