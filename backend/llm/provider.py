<<<<<<< HEAD
"""Configurable generation provider for any OpenAI-compatible chat endpoint.

Works with vLLM, Together AI, Hugging Face Inference Providers, OpenRouter, Ollama, etc.
Set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL (default ``Qwen/Qwen3.5-9B``). Secrets are only
read from the environment and never returned or logged.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from config import settings
from errors import LLMUnavailable

logger = logging.getLogger(__name__)
_THINK_RE = re.compile(r"<think>.*?</think>", re.S)
=======
"""Generation provider. Remote OpenAI-compatible endpoints are opt-in."""
from config import settings
>>>>>>> origin/main


class LLMProvider:
    @property
<<<<<<< HEAD
    def configured(self) -> bool:
        return settings.llm_configured

    @property
    def backend(self) -> str:
        return "openai-compatible" if self.configured else "none"

    def info(self) -> Dict[str, object]:
        return {"configured": self.configured, "model": settings.llm_model if self.configured else None,
                "base_url_set": bool(settings.llm_base_url), "api_key_set": bool(settings.llm_api_key)}

    def chat(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> str:
        """Return the assistant text or raise :class:`LLMUnavailable` (not configured, timeout, upstream error)."""
        if not self.configured:
            raise LLMUnavailable("No language model is configured. Set LLM_BASE_URL and LLM_API_KEY.")
        try:
            from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
        except ImportError as exc:
            raise LLMUnavailable("The 'openai' package is not installed.") from exc
        client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key, timeout=settings.llm_timeout_seconds, max_retries=1)
        try:
            result = client.chat.completions.create(
                model=settings.llm_model, messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens or settings.llm_max_tokens,
                temperature=settings.llm_temperature if temperature is None else temperature,
            )
        except APITimeoutError as exc:
            raise LLMUnavailable("The language model timed out. Try again or increase LLM_TIMEOUT_SECONDS.") from exc
        except APIConnectionError as exc:
            raise LLMUnavailable("Could not reach the language model endpoint.") from exc
        except APIStatusError as exc:
            logger.warning("LLM returned HTTP %s", exc.status_code)
            raise LLMUnavailable(f"The language model endpoint returned an error (HTTP {exc.status_code}).") from exc
        except Exception as exc:
            logger.exception("Unexpected LLM failure")
            raise LLMUnavailable("The language model request failed.") from exc
        text = (result.choices[0].message.content or "") if result.choices else ""
        text = _THINK_RE.sub("", text).strip()
        if not text:
            raise LLMUnavailable("The language model returned an empty response.")
        return text
=======
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
>>>>>>> origin/main


llm = LLMProvider()
