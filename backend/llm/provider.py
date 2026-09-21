"""Generation provider. Remote OpenAI-compatible endpoints are opt-in."""
from config import settings


class LLMProvider:
    @property
    def backend(self) -> str:
        return "openai-compatible" if settings.llm_base_url and settings.llm_api_key else "extractive-fallback"

    def generate(self, prompt: str, context: str = "") -> str:
        if settings.llm_base_url and settings.llm_api_key:
            try:
                from openai import OpenAI
                client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
                result = client.chat.completions.create(model=settings.llm_model, messages=[
                    {"role": "system", "content": "Answer only from supplied research context. State uncertainty when unsupported."},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {prompt}"},
                ], temperature=0.2)
                return result.choices[0].message.content or "No answer was generated."
            except Exception:
                pass
        return ""


llm = LLMProvider()
