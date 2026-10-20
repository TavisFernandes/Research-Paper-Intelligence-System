"""Configurable generation provider for any OpenAI-compatible chat endpoint.

Works with vLLM, Together AI, Hugging Face Inference Providers, OpenRouter, Ollama, etc.
Set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL (default ``Qwen/Qwen3.5-9B``). Secrets are only
read from the environment and never returned or logged.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from config import Settings, settings
from errors import LLMUnavailable

logger = logging.getLogger(__name__)
_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


class LLMProvider:
    def __init__(self, config: Optional[Settings] = None) -> None:
        self._settings = config if config is not None else settings

    @property
    def configured(self) -> bool:
        return self._settings.llm_configured

    @property
    def backend(self) -> str:
        if self._settings.llm_primary_configured:
            return "openai-compatible"
        if self._settings.llm_fallback_configured:
            return self._backend_name(self._settings.llm_fallback_base_url)
        return "none"

    def info(self) -> Dict[str, object]:
        primary_configured = self._settings.llm_primary_configured
        fallback_configured = self._settings.llm_fallback_configured
        return {
            "configured": self.configured,
            "primary_configured": primary_configured,
            "model": self._settings.llm_model if primary_configured else self._settings.llm_fallback_model if fallback_configured else None,
            "base_url_set": bool(self._settings.llm_base_url),
            "api_key_set": bool(self._settings.llm_api_key),
            "fallback_configured": fallback_configured,
            "fallback_model": self._settings.llm_fallback_model if fallback_configured else None,
        }

    def chat(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None, temperature: Optional[float] = None,
             *, timeout_seconds: Optional[float] = None) -> str:
        """Return the assistant text or raise :class:`LLMUnavailable` (not configured, timeout, upstream error)."""
        return self.chat_with_info(
            messages, max_tokens=max_tokens, temperature=temperature, timeout_seconds=timeout_seconds,
        )[0]

    def chat_with_info(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None,
                       temperature: Optional[float] = None, *,
                       timeout_seconds: Optional[float] = None) -> Tuple[str, Dict[str, object]]:
        """Generate text and report which configured endpoint returned it."""
        providers = []
        if self._settings.llm_primary_configured:
            providers.append({
                "base_url": self._settings.llm_base_url,
                "api_key": self._settings.llm_api_key,
                "model": self._settings.llm_model,
                "timeout": timeout_seconds if timeout_seconds is not None else self._settings.llm_timeout_seconds,
                "max_tokens": max_tokens or self._settings.llm_max_tokens,
                "fallback": False,
            })
        if self._settings.llm_fallback_configured:
            # Honour the caller's interactive-answer budget for local and secondary fallbacks.
            fallback_timeout = self._settings.llm_fallback_timeout_seconds
            if timeout_seconds is not None:
                fallback_timeout = min(fallback_timeout, float(timeout_seconds))
            providers.append({
                "base_url": self._settings.llm_fallback_base_url,
                "api_key": self._settings.llm_fallback_api_key,
                "model": self._settings.llm_fallback_model,
                "timeout": fallback_timeout,
                "max_tokens": max_tokens or self._settings.llm_fallback_max_tokens,
                "fallback": True,
            })
        if not providers:
            raise LLMUnavailable("No language model is configured. Set LLM_BASE_URL and LLM_API_KEY.")

        failures = []
        for provider in providers:
            try:
                text = self._chat_endpoint(provider, messages, temperature)
                used_fallback = bool(provider["fallback"])
                generation: Dict[str, object] = {
                    "backend": self._backend_name(str(provider["base_url"])),
                    "model": provider["model"],
                    "fallback_used": used_fallback,
                }
                if used_fallback:
                    generation["warning"] = (
                        "The cloud language model is not configured; the local fallback was used."
                        if not self._settings.llm_primary_configured
                        else "The cloud language model was unavailable; the local fallback was used."
                    )
                return text, generation
            except LLMUnavailable as exc:
                failures.append(exc.public_message)
                if not exc.retryable:
                    raise
        if len(failures) == 1:
            raise LLMUnavailable(failures[0])
        raise LLMUnavailable(f"{failures[0]} The configured fallback also failed: {failures[1]}")

    def _chat_endpoint(self, provider: Dict[str, object], messages: List[Dict[str, str]],
                       temperature: Optional[float]) -> str:
        base_url = str(provider["base_url"])
        # Qwen3 via Ollama's OpenAI-compatible /v1 path ignores think=false and spends the
        # whole token budget in ``reasoning`` with empty ``content``. Use native /api/chat.
        if self._is_local_ollama(base_url):
            return self._chat_ollama_native(provider, messages, temperature)
        return self._chat_openai_compatible(provider, messages, temperature)

    def _chat_ollama_native(self, provider: Dict[str, object], messages: List[Dict[str, str]],
                            temperature: Optional[float]) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise LLMUnavailable("The 'httpx' package is not installed.") from exc

        base_url = str(provider["base_url"]).rstrip("/")
        root = base_url[:-3] if base_url.endswith("/v1") else base_url
        model = str(provider["model"])
        temp = self._settings.llm_temperature if temperature is None else temperature
        payload: Dict[str, object] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temp, "num_predict": int(provider["max_tokens"])},
        }
        if model.startswith("qwen3"):
            payload["think"] = False
        try:
            response = httpx.post(f"{root}/api/chat", json=payload, timeout=float(provider["timeout"]))
        except httpx.TimeoutException as exc:
            raise LLMUnavailable(
                "The language model timed out. Try again or increase LLM_FALLBACK_TIMEOUT_SECONDS."
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailable("Could not reach the language model endpoint.") from exc
        if response.status_code >= 400:
            logger.warning("Ollama returned HTTP %s", response.status_code)
            raise LLMUnavailable(
                f"The language model endpoint returned an error (HTTP {response.status_code}).",
                retryable=response.status_code >= 500,
            )
        try:
            body = response.json()
            text = str((body.get("message") or {}).get("content") or "")
        except Exception as exc:
            raise LLMUnavailable("The language model returned an invalid response.") from exc
        text = _THINK_RE.sub("", text).strip()
        if not text:
            raise LLMUnavailable("The language model returned an empty response.")
        return text

    def _chat_openai_compatible(self, provider: Dict[str, object], messages: List[Dict[str, str]],
                                temperature: Optional[float]) -> str:
        try:
            from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
        except ImportError as exc:
            raise LLMUnavailable("The 'openai' package is not installed.") from exc

        model = str(provider["model"])
        options: Dict[str, object] = {
            "model": model,
            "messages": messages,  # type: ignore[arg-type]
            "max_tokens": int(provider["max_tokens"]),
            "temperature": self._settings.llm_temperature if temperature is None else temperature,
        }
        if model.startswith("qwen3.5-"):
            options["extra_body"] = {"enable_thinking": False}
        elif model.startswith("gemini-3"):
            options["reasoning_effort"] = "low"
        client = OpenAI(
            base_url=str(provider["base_url"]),
            api_key=str(provider["api_key"]),
            timeout=float(provider["timeout"]),
            max_retries=0,
        )
        try:
            result = client.chat.completions.create(**options)
        except APITimeoutError as exc:
            setting = "LLM_FALLBACK_TIMEOUT_SECONDS" if provider["fallback"] else "LLM_TIMEOUT_SECONDS"
            raise LLMUnavailable(f"The language model timed out. Try again or increase {setting}.") from exc
        except APIConnectionError as exc:
            raise LLMUnavailable("Could not reach the language model endpoint.") from exc
        except APIStatusError as exc:
            logger.warning("LLM returned HTTP %s", exc.status_code)
            retryable = exc.status_code >= 500
            raise LLMUnavailable(
                f"The language model endpoint returned an error (HTTP {exc.status_code}).",
                retryable=retryable,
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected LLM failure")
            raise LLMUnavailable("The language model request failed.") from exc
        text = (result.choices[0].message.content or "") if result.choices else ""
        text = _THINK_RE.sub("", text).strip()
        if not text:
            raise LLMUnavailable("The language model returned an empty response.")
        return text

    @staticmethod
    def _is_local_ollama(base_url: str) -> bool:
        parsed = urlsplit(base_url)
        return parsed.hostname in {"localhost", "127.0.0.1"} and parsed.port == 11434

    @classmethod
    def _backend_name(cls, base_url: str) -> str:
        return "ollama-local-fallback" if cls._is_local_ollama(base_url) else "openai-compatible"


llm = LLMProvider()
