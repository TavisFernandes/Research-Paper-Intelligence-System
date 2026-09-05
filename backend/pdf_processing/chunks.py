from typing import Dict, List


def create_chunks(sections: List[Dict[str, object]], chunk_size: int = 1200, overlap: int = 150) -> List[Dict[str, object]]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be smaller than chunk_size")
    chunks: List[Dict[str, object]] = []
    for section in sections:
        text = str(section["text"])
        start = 0
        index = 1
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    "paper_id": section["paper_id"],
                    "chunk_id": f"{section['paper_id']}_{section['section_name']}_{index:03d}",
                    "section_name": section["section_name"],
                    "page_start": section["page_start"],
                    "page_end": section["page_end"],
                    "text": chunk_text,
                })
                index += 1
            if end == len(text):
                break
            start = end - overlap
    return chunks
