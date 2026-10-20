import pytest

from config import settings
from errors import InvalidInputError, LLMUnavailable, SummarizationUnavailable
from llm import LLMProvider, get_chat_llm
from pdf_processing import storage
from summarization.led import extractive_summary, rouge, summarize, summarize_paper
from summarization.led import service as led_service


# ------------------------------------------------------------------------------- LLM
def test_llm_not_configured_raises(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "")
    with pytest.raises(LLMUnavailable, match="No language model"):
        LLMProvider().chat([{"role": "user", "content": "hi"}])


def _configure(monkeypatch):
    monkeypatch.setattr(settings, "llm_base_url", "http://127.0.0.1:1/v1")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "test-primary")
    monkeypatch.setattr(settings, "llm_fallback_base_url", "")
    monkeypatch.setattr(settings, "llm_fallback_api_key", "")
    monkeypatch.setattr(settings, "llm_fallback_model", "")


def test_llm_unreachable_endpoint_maps_to_unavailable(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "llm_timeout_seconds", 2.0)
    with pytest.raises(LLMUnavailable, match="Could not reach|timed out"):
        LLMProvider().chat([{"role": "user", "content": "hi"}])


def test_llm_timeout_and_think_stripping(monkeypatch):
    import openai

    try:
        import httpx2 as httpx_mod
    except ImportError:
        import httpx as httpx_mod
    _configure(monkeypatch)

    class Timeout:
        def __init__(self, **kw):
            self.chat = type("C", (), {"completions": type("X", (), {"create": staticmethod(lambda **k: (_ for _ in ()).throw(openai.APITimeoutError(request=httpx_mod.Request("POST", "http://x"))))})()})()

    monkeypatch.setattr(openai, "OpenAI", Timeout)
    with pytest.raises(LLMUnavailable, match="timed out"):
        LLMProvider().chat([{"role": "user", "content": "hi"}])

    class Ok:
        def __init__(self, **kw):
            msg = type("M", (), {"content": "<think>secret</think>Final answer [1]."})()
            resp = type("R", (), {"choices": [type("Ch", (), {"message": msg})()]})()
            self.chat = type("C", (), {"completions": type("X", (), {"create": staticmethod(lambda **k: resp)})()})()

    monkeypatch.setattr(openai, "OpenAI", Ok)
    assert LLMProvider().chat([{"role": "user", "content": "hi"}]) == "Final answer [1]."


def test_api_key_is_never_in_info_or_repr(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "llm_fallback_api_key", "fallback-test-key")
    assert "test-key" not in str(LLMProvider().info()) and "test-key" not in repr(settings)
    assert "fallback-test-key" not in repr(settings)


def test_chat_llm_uses_gemini_without_changing_shared_provider(monkeypatch):
    import openai

    _configure(monkeypatch)
    monkeypatch.setattr(settings, "gemini_api_key", "gemini-test-key")
    monkeypatch.setattr(settings, "gemini_model", "gemini-test-model")
    clients = []

    class FakeOpenAI:
        def __init__(self, **kwargs):
            clients.append(kwargs)
            message = type("Message", (), {"content": "Grounded answer [1]."})()
            choice = type("Choice", (), {"message": message})()
            response = type("Response", (), {"choices": [choice]})()
            self.chat = type(
                "Chat",
                (),
                {"completions": type("Completions", (), {"create": staticmethod(lambda **options: response)})()},
            )()

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    shared_provider = LLMProvider()
    chat_provider = get_chat_llm(shared_provider)

    assert chat_provider is not shared_provider
    assert shared_provider.info()["model"] == "test-primary"
    assert chat_provider.info()["model"] == "gemini-test-model"
    assert "gemini-test-key" not in str(chat_provider.info())
    assert "gemini-test-key" not in repr(chat_provider._settings)
    assert chat_provider.chat([{"role": "user", "content": "hi"}]) == "Grounded answer [1]."
    assert clients[0]["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert clients[0]["api_key"] == "gemini-test-key"


def test_llm_uses_local_fallback_when_primary_is_unavailable(monkeypatch):
    import httpx
    import openai

    _configure(monkeypatch)
    monkeypatch.setattr(settings, "llm_fallback_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "llm_fallback_api_key", "ollama")
    monkeypatch.setattr(settings, "llm_fallback_model", "qwen3:8b")
    native_calls = []

    class FakeOpenAI:
        def __init__(self, base_url, **kwargs):
            self.base_url = base_url

            def create(**options):
                raise openai.APIConnectionError(request=httpx.Request("POST", self.base_url))

            self.chat = type("Chat", (), {"completions": type("Completions", (), {"create": staticmethod(create)})()})()

    def fake_native(provider, messages, temperature):
        native_calls.append(provider)
        return "Grounded answer [1]."

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(LLMProvider, "_chat_ollama_native", staticmethod(fake_native))
    answer, generation = LLMProvider().chat_with_info([{"role": "user", "content": "hi"}])

    assert answer == "Grounded answer [1]."
    assert generation["model"] == "qwen3:8b"
    assert generation["fallback_used"] is True
    assert generation["backend"] == "ollama-local-fallback"
    assert native_calls[0]["max_tokens"] == settings.llm_fallback_max_tokens
    assert native_calls[0]["model"] == "qwen3:8b"


def test_llm_does_not_fallback_for_cloud_auth_errors(monkeypatch):
    import httpx
    import openai

    _configure(monkeypatch)
    monkeypatch.setattr(settings, "llm_fallback_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "llm_fallback_api_key", "ollama")
    monkeypatch.setattr(settings, "llm_fallback_model", "qwen3:8b")
    calls = []

    class FakeOpenAI:
        def __init__(self, base_url, **kwargs):
            self.base_url = base_url

            def create(**options):
                calls.append(self.base_url)
                request = httpx.Request("POST", self.base_url)
                response = httpx.Response(401, request=request)
                raise openai.AuthenticationError("invalid API key", response=response, body=None)

            self.chat = type("Chat", (), {"completions": type("Completions", (), {"create": staticmethod(create)})()})()

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    with pytest.raises(LLMUnavailable, match="HTTP 401"):
        LLMProvider().chat([{"role": "user", "content": "hi"}])
    assert calls == [settings.llm_base_url]


def test_llm_uses_local_fallback_when_cloud_key_is_missing(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "llm_base_url", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_fallback_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "llm_fallback_api_key", "ollama")
    monkeypatch.setattr(settings, "llm_fallback_model", "qwen3:8b")
    provider = LLMProvider()
    calls = []

    def chat_endpoint(endpoint, messages, temperature):
        calls.append(endpoint)
        return "Local answer [1]."

    monkeypatch.setattr(provider, "_chat_endpoint", chat_endpoint)
    answer, generation = provider.chat_with_info([{"role": "user", "content": "hi"}])

    assert answer == "Local answer [1]."
    assert generation["fallback_used"] is True
    assert generation["model"] == "qwen3:8b"
    assert len(calls) == 1 and calls[0]["fallback"] is True


def test_llm_fallback_remains_enabled_for_other_features(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_fallback_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "llm_fallback_api_key", "ollama")
    monkeypatch.setattr(settings, "llm_fallback_model", "qwen3:8b")
    provider = LLMProvider()
    calls = []

    def chat_endpoint(endpoint, messages, temperature):
        calls.append(endpoint["fallback"])
        return "Fallback answer."

    monkeypatch.setattr(provider, "_chat_endpoint", chat_endpoint)
    answer, generation = provider.chat_with_info([{"role": "user", "content": "hi"}])

    assert answer == "Fallback answer."
    assert generation["fallback_used"] is True
    assert calls == [True]


def test_qwen35_cloud_request_disables_thinking(monkeypatch):
    import openai

    _configure(monkeypatch)
    monkeypatch.setattr(settings, "llm_base_url", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setattr(settings, "llm_model", "qwen3.5-plus")
    calls = []
    client_options = []

    class FakeOpenAI:
        def __init__(self, **kwargs):
            client_options.append(kwargs)

            def create(**options):
                calls.append(options)
                message = type("Message", (), {"content": "Grounded answer [1]."})()
                choice = type("Choice", (), {"message": message})()
                return type("Response", (), {"choices": [choice]})()

            self.chat = type("Chat", (), {"completions": type("Completions", (), {"create": staticmethod(create)})()})()

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    answer = LLMProvider().chat([{"role": "user", "content": "hi"}])

    assert answer == "Grounded answer [1]."
    assert calls[0]["model"] == "qwen3.5-plus"
    assert calls[0]["extra_body"] == {"enable_thinking": False}
    assert calls[0]["max_tokens"] == settings.llm_max_tokens
    assert client_options[0]["timeout"] == settings.llm_timeout_seconds

    LLMProvider().chat([{"role": "user", "content": "hi"}], timeout_seconds=16)
    assert client_options[1]["timeout"] == 16


def test_gemini_chat_uses_low_reasoning(monkeypatch):
    import openai

    _configure(monkeypatch)
    monkeypatch.setattr(settings, "llm_model", "gemini-3.1-flash-lite")
    calls = []

    class FakeOpenAI:
        def __init__(self, **kwargs):
            def create(**options):
                calls.append(options)
                message = type("Message", (), {"content": "Grounded answer [1]."})()
                choice = type("Choice", (), {"message": message})()
                return type("Response", (), {"choices": [choice]})()

            self.chat = type(
                "Chat",
                (),
                {"completions": type("Completions", (), {"create": staticmethod(create)})()},
            )()

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    assert LLMProvider().chat([{"role": "user", "content": "hi"}]) == "Grounded answer [1]."
    assert calls[0]["reasoning_effort"] == "low"
    assert calls[0]["max_tokens"] == settings.llm_max_tokens


def test_local_only_qa_uses_fallback_timeout_budget(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_fallback_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "llm_fallback_api_key", "ollama")
    monkeypatch.setattr(settings, "llm_fallback_model", "qwen3:4b")
    monkeypatch.setattr(settings, "llm_fallback_timeout_seconds", 90.0)
    seen = []

    def fake_native(provider, messages, temperature):
        seen.append(provider)
        return "Local answer [1]."

    monkeypatch.setattr(LLMProvider, "_chat_ollama_native", staticmethod(fake_native))
    # Local-only QA still respects the caller budget so the UI stays within ~20s.
    LLMProvider().chat([{"role": "user", "content": "hi"}], timeout_seconds=18)
    assert seen[0]["timeout"] == 18.0


def test_qa_timeout_caps_fallback_when_cloud_is_configured(monkeypatch):
    import openai

    _configure(monkeypatch)
    monkeypatch.setattr(settings, "llm_fallback_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "llm_fallback_api_key", "ollama")
    monkeypatch.setattr(settings, "llm_fallback_model", "qwen3:4b")
    monkeypatch.setattr(settings, "llm_fallback_timeout_seconds", 90.0)
    cloud_timeouts = []
    native_timeouts = []

    class FakeOpenAI:
        def __init__(self, **kwargs):
            cloud_timeouts.append(kwargs.get("timeout"))

            def create(**options):
                raise openai.APITimeoutError(request=type("R", (), {"method": "POST", "url": "http://x"})())

            self.chat = type("Chat", (), {"completions": type("Completions", (), {"create": staticmethod(create)})()})()

    def fake_native(provider, messages, temperature):
        native_timeouts.append(provider["timeout"])
        return "Local answer [1]."

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(LLMProvider, "_chat_ollama_native", staticmethod(fake_native))
    LLMProvider().chat([{"role": "user", "content": "hi"}], timeout_seconds=16)
    assert cloud_timeouts[0] == 16
    assert native_timeouts[0] == 16.0


def test_local_ollama_qwen_disables_reasoning(monkeypatch):
    import httpx

    _configure(monkeypatch)
    monkeypatch.setattr(settings, "llm_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "llm_api_key", "ollama")
    monkeypatch.setattr(settings, "llm_model", "qwen3:8b")
    calls = []

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"message": {"content": "Grounded answer [1]."}}

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)
    answer = LLMProvider().chat([{"role": "user", "content": "hi"}])

    assert answer == "Grounded answer [1]."
    assert calls[0]["url"] == "http://localhost:11434/api/chat"
    assert calls[0]["json"]["think"] is False
    assert calls[0]["json"]["model"] == "qwen3:8b"


# -------------------------------------------------------------------- summarisation
LONG = " ".join(f"Sentence {i} discusses retrieval of scientific evidence with models." for i in range(40)) + " The key finding is that fine-tuning improves recall substantially."


def test_extractive_summary_is_bounded_and_ordered():
    summary, sentences = extractive_summary(LONG, 3)
    assert len(sentences) == 3 and all(s in LONG for s in sentences)
    assert [LONG.index(s) for s in sentences] == sorted(LONG.index(s) for s in sentences)


def test_summarize_labels_backend_when_led_disabled():
    out = summarize(LONG, 2)
    assert out["backend"] == "extractive" and out["degraded"] is False and "disabled" in out["note"]
    assert summarize("   ")["backend"] == "none"


def test_led_enabled_but_unavailable_falls_back_and_says_so(monkeypatch):
    monkeypatch.setattr(settings, "enable_led", True)
    monkeypatch.setattr(led_service._led, "_load", lambda: (_ for _ in ()).throw(SummarizationUnavailable("LED model unavailable.")))
    out = summarize(LONG, 2)
    assert out["backend"] == "extractive" and out["degraded"] is True and "LED model unavailable" in out["note"]


def test_led_windowing_processes_the_whole_document(monkeypatch):
    """Map-reduce: a text longer than the window is split, every window is summarised, nothing is truncated."""
    led = led_service.LedSummarizer()
    monkeypatch.setattr(led, "_load", lambda: None)
    monkeypatch.setattr(led, "count_tokens", lambda text: len(text.split()))
    seen = []

    def fake_generate(text, max_new, min_new):
        seen.append(text)
        return "SUM(" + " ".join(text.split()[:3]) + ")"

    monkeypatch.setattr(led, "_generate", fake_generate)
    monkeypatch.setattr(settings, "led_window_tokens", 100)
    monkeypatch.setattr(settings, "led_max_input_tokens", 300)
    text = " ".join(f"Word{i} is here today." for i in range(200))  # 800 tokens > the 300-token model window
    result = led.summarize(text)
    assert result["windows"] >= 3 and result["reduction_passes"] >= 1
    window_inputs = [s for s in seen if "SUM(" not in s]
    covered = " ".join(window_inputs)
    assert "Word0 " in covered and "Word199" in covered  # beginning and end both reached


def test_paper_summary_structure(paper_a):
    out = summarize_paper(paper_a)
    assert out["found"] and out["summary"] and out["backend"] == "extractive"
    assert [s["section_name"] for s in out["sections"]][:2] == ["ABSTRACT", "INTRODUCTION"]
    assert out["sections"][0]["pages"] == [1, 1]
    assert "PubMedQA" in out["highlights"]["datasets"]
    missing = summarize_paper(paper_a, "RELATED_WORK")
    assert missing["found"] is False and "not identified" in missing["note"]
    one = summarize_paper(paper_a, "RESULTS")
    assert one["found"] and "0.91" in one["summary"]


def test_rouge_values_and_validation():
    perfect = rouge(["the cat sat on the mat"], ["the cat sat on the mat"])
    assert perfect["rouge1"] == perfect["rouge2"] == perfect["rougeL"] == 1.0
    partial = rouge(["the cat sat"], ["the cat sat on the mat"])
    assert 0 < partial["rouge1"] < 1 and partial["n_examples"] == 1
    for bad in ((["a"], []), ([], []), (["a"], [" "])):
        with pytest.raises(InvalidInputError):
            rouge(*bad)


# ------------------------------------------------------------------------- storage
def test_storage_roundtrip_listing_and_ids():
    paper = {"paper_id": "P001", "filename": "x.pdf", "content_sha256": "abc"}
    storage.save_paper(paper)
    assert storage.load_paper("P001")["filename"] == "x.pdf"
    assert [p["paper_id"] for p in storage.list_papers()] == ["P001"]  # regression: P### ids must be listed
    assert storage.find_by_hash("abc")["paper_id"] == "P001" and storage.find_by_hash("zzz") is None
    assert storage.next_paper_id() == "P002"
    storage.save_source("P002", "y.pdf", b"%PDF-")
    assert storage.next_paper_id() == "P003"  # reserved by an in-flight upload
    assert storage.delete_paper("P001") is True and storage.delete_paper("P001") is False


@pytest.mark.parametrize("bad", ["../etc/passwd", "a/b", "", "a b", ".hidden", "x" * 80])
def test_path_traversal_ids_rejected(bad):
    with pytest.raises(InvalidInputError):
        storage.validate_paper_id(bad)


def test_corrupt_json_is_skipped():
    (storage.storage_dir() / "P009.json").write_text("{not json")
    assert storage.list_papers() == [] and storage.load_paper("P009") is None
