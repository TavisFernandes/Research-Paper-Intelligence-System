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
