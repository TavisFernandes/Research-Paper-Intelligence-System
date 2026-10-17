<<<<<<< HEAD
<<<<<<< HEAD
"""Long-document summarisation: LED (token-aware, windowed) with an honest extractive fallback.

* LED is loaded once (lazily) and only when ``ENABLE_LED=true``. ``LED_MODEL`` may be a Hugging Face id
  (default ``allenai/led-base-16384``) or a local fine-tuned checkpoint directory. An optional
  ``LED_STATE_DICT_PATH`` loads a ``.pth`` state dict (as saved by the team's training notebook) on top.
* Papers longer than the model window are split on sentence boundaries into windows, each window is
  summarised, and the partial summaries are summarised again (map-reduce). Nothing is silently truncated.
* If LED cannot run, an extractive summary is returned and labelled ``backend: "extractive"``.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple

from config import settings
from errors import SummarizationUnavailable
from pdf_processing.preprocess import segment_sentences

logger = logging.getLogger(__name__)

SUMMARY_SECTION_ORDER = ["ABSTRACT", "INTRODUCTION", "RELATED_WORK", "METHODOLOGY", "DATASET", "EXPERIMENTS", "RESULTS",
                         "DISCUSSION", "LIMITATIONS", "CONCLUSION", "FUTURE_WORK"]
_EXCLUDED = {"REFERENCES", "ACKNOWLEDGMENTS", "APPENDIX"}


# --------------------------------------------------------------------------- extractive
def extractive_summary(text: str, max_sentences: int = 5) -> Tuple[str, List[str]]:
    """Centrality-based extractive summary (TF-IDF cosine to the document centroid), in document order."""
    sentences = [s for s in segment_sentences(text) if len(s.split()) >= 5]
    if not sentences:
        return "", []
    if len(sentences) <= max_sentences:
        return " ".join(sentences), sentences
    scores: List[float]
    try:
        import numpy as np
        from sklearn.feature_extraction.text import TfidfVectorizer

        matrix = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit_transform(sentences)
        centroid = np.asarray(matrix.mean(axis=0))
        scores = (matrix @ centroid.T).ravel().tolist()
    except Exception:
        freq: Dict[str, int] = {}
        for s in sentences:
            for w in re.findall(r"[a-z]{4,}", s.lower()):
                freq[w] = freq.get(w, 0) + 1
        scores = [sum(freq.get(w, 0) for w in re.findall(r"[a-z]{4,}", s.lower())) / (len(s.split()) or 1) for s in sentences]
    top = sorted(sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)[:max_sentences])
    chosen = [sentences[i] for i in top]
    return " ".join(chosen), chosen


# ------------------------------------------------------------------------------- LED
class LedSummarizer:
    def __init__(self) -> None:
        self._tokenizer: Any = None
        self._model: Any = None
        self._device = "cpu"
        self._lock = threading.Lock()
        self.error: Optional[str] = None

    def available(self) -> bool:
        try:
            self._load()
            return True
        except SummarizationUnavailable:
            return False

    def _load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            if self.error:
                raise SummarizationUnavailable(self.error)
            try:
                import torch
                from transformers import AutoTokenizer, LEDForConditionalGeneration

                tokenizer = AutoTokenizer.from_pretrained(settings.led_model)
                model = LEDForConditionalGeneration.from_pretrained(settings.led_model)
                state_path = os.getenv("LED_STATE_DICT_PATH", "")
                if state_path:
                    model.load_state_dict(torch.load(state_path, map_location="cpu"))
                device = "cuda" if torch.cuda.is_available() else "cpu"
                model.to(device).eval()
                self._tokenizer, self._model, self._device = tokenizer, model, device
            except Exception as exc:
                self.error = f"LED model unavailable ({type(exc).__name__}). Install torch and transformers and check LED_MODEL."
                logger.warning("%s", self.error)
                raise SummarizationUnavailable(self.error) from exc

    def count_tokens(self, text: str) -> int:
        self._load()
        return len(self._tokenizer(text, add_special_tokens=False)["input_ids"])

    def _generate(self, text: str, max_new: int, min_new: int) -> str:
        import torch

        encoded = self._tokenizer(text, max_length=settings.led_max_input_tokens, truncation=True, return_tensors="pt").to(self._device)
        global_attention = torch.zeros_like(encoded["input_ids"])
        global_attention[:, 0] = 1
        with torch.no_grad():
            ids = self._model.generate(encoded["input_ids"], attention_mask=encoded["attention_mask"], global_attention_mask=global_attention,
                                       max_length=max_new, min_length=min(min_new, max_new - 1), num_beams=4, length_penalty=2.0,
                                       no_repeat_ngram_size=3, early_stopping=True)
        return self._tokenizer.decode(ids[0], skip_special_tokens=True).strip()

    def _windows(self, text: str) -> List[str]:
        windows: List[str] = []
        current: List[str] = []
        used = 0
        for sentence in segment_sentences(text):
            n = self.count_tokens(sentence)
            if current and used + n > settings.led_window_tokens:
                windows.append(" ".join(current))
                current, used = [], 0
            current.append(sentence)
            used += n
        if current:
            windows.append(" ".join(current))
        return windows

    def summarize(self, text: str) -> Dict[str, Any]:
        self._load()
        limit = min(settings.led_max_input_tokens, settings.led_window_tokens + 2000)
        total = self.count_tokens(text)
        passes, windows_total, current = 0, 1, text
        while self.count_tokens(current) > limit and passes < 4:
            windows = self._windows(current)
            windows_total = max(windows_total, len(windows))
            current = "\n".join(self._generate(w, settings.led_max_summary_tokens, settings.led_min_summary_tokens) for w in windows)
            passes += 1
        summary = self._generate(current, settings.led_max_summary_tokens, settings.led_min_summary_tokens)
        return {"summary": summary, "input_tokens": total, "windows": windows_total, "reduction_passes": passes}


_led = LedSummarizer()


def led_status() -> Dict[str, object]:
    return {"enabled": settings.enable_led, "model": settings.led_model, "loaded": _led._model is not None, "error": _led.error}


def summarize(text: str, max_sentences: int = 5) -> Dict[str, Any]:
    """Summarise arbitrary text. Returns ``{summary, backend, degraded, ...}``."""
    text = (text or "").strip()
    if not text:
        return {"summary": "", "backend": "none", "degraded": False, "note": "No text to summarise."}
    note = "LED is disabled (set ENABLE_LED=true); extractive summary shown."
    if settings.enable_led:
        try:
            result = _led.summarize(text)
            return {**result, "backend": "led", "model": settings.led_model, "degraded": False}
        except SummarizationUnavailable as exc:
            note = f"{exc.public_message} Falling back to an extractive summary."
        except Exception:
            logger.exception("LED generation failed")
            note = "LED generation failed; falling back to an extractive summary."
    summary, sentences = extractive_summary(text, max_sentences)
    return {"summary": summary, "backend": "extractive", "degraded": settings.enable_led, "sentence_count": len(sentences), "note": note}


def summarize_paper(paper: Dict[str, Any], section_name: Optional[str] = None, max_sentences: int = 5,
                    per_section: bool = True) -> Dict[str, Any]:
    """Summary of a whole paper or one section, with per-section summaries and page provenance."""
    sections: Sequence[Dict[str, Any]] = paper.get("sections", [])
    if section_name:
        picked = [s for s in sections if s["section_name"] == section_name]
        if not picked:
            return {"paper_id": paper["paper_id"], "section_name": section_name, "found": False,
                    "summary": "", "note": f"Section '{section_name}' was not identified in this paper."}
        result = summarize("\n".join(str(s["text"]) for s in picked), max_sentences)
        return {"paper_id": paper["paper_id"], "section_name": section_name, "found": True,
                "pages": [min(s["page_start"] for s in picked), max(s["page_end"] for s in picked)], **result}
    usable = [s for s in sections if s["section_name"] not in _EXCLUDED]
    known = [s for s in usable if s["section_name"] != "UNKNOWN"]
    body = known or usable
    overall = summarize("\n".join(str(s["text"]) for s in body), max_sentences)
    out: Dict[str, Any] = {"paper_id": paper["paper_id"], "title": paper.get("title"), "section_name": None, "found": True, "overall": overall,
                           "sections": [], "highlights": _highlights(paper)}
    out["summary"] = overall["summary"]
    out["backend"] = overall["backend"]
    if per_section:
        for name in SUMMARY_SECTION_ORDER:
            group = [s for s in sections if s["section_name"] == name]
            if group:
                res = summarize("\n".join(str(s["text"]) for s in group), max(2, max_sentences // 2))
                out["sections"].append({"section_name": name, "pages": [min(s["page_start"] for s in group), max(s["page_end"] for s in group)],
                                        "summary": res["summary"], "backend": res["backend"]})
    return out


def _highlights(paper: Dict[str, Any]) -> Dict[str, List[str]]:
    """Datasets/models/metrics explicitly detected in the text (NER output; never inferred)."""
    groups = {"datasets": "DATASET", "models": "MODEL", "algorithms": "ALGORITHM", "metrics": "METRIC", "organizations": "ORGANIZATION"}
    entities = paper.get("analysis", {}).get("entities", [])
    return {key: [e["text"] for e in entities if e["label"] == label][:8] for key, label in groups.items()}
=======
=======
>>>>>>> origin/main
"""Long-document summary service; LED is loaded lazily, extractive summary is always available."""
from pdf_processing.preprocess import segment_sentences
from config import settings


def summarize(text: str, max_sentences: int = 5) -> dict[str, object]:
    sentences = segment_sentences(text)
    if not sentences:
        return {"summary": "No extractable text is available.", "backend": "extractive", "sentence_count": 0}
    # LED loading is intentionally lazy and only enabled by explicit environment choice.
    if __import__("os").getenv("ENABLE_LED", "false").lower() == "true":
        try:
            from transformers import pipeline
            model = pipeline("summarization", model=settings.led_model)
            result = model(text[:60_000], max_length=256, min_length=40, do_sample=False)[0]["summary_text"]
            return {"summary": result, "backend": "led", "sentence_count": len(sentences)}
        except Exception:
            pass
    ranked = sorted(enumerate(sentences), key=lambda item: len(item[1]), reverse=True)[:max_sentences]
    ranked.sort()
    return {"summary": " ".join(sentence for _, sentence in ranked), "backend": "extractive", "sentence_count": len(sentences)}
<<<<<<< HEAD
>>>>>>> origin/main
=======
>>>>>>> origin/main
