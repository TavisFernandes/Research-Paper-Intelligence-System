from dataclasses import replace
from typing import Optional

from config import settings
from .provider import LLMProvider, llm

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def get_chat_llm(default_provider: Optional[LLMProvider] = None) -> LLMProvider:
    if not settings.gemini_api_key:
        return default_provider if default_provider is not None else llm
    chat_settings = replace(
        settings,
        llm_base_url=_GEMINI_BASE_URL,
        llm_api_key=settings.gemini_api_key,
        llm_model=settings.gemini_model,
    )
    return LLMProvider(chat_settings)


__all__ = ["LLMProvider", "get_chat_llm", "llm"]
