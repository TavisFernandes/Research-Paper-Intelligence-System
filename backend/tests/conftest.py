import os

# Must be set before application modules import settings.
os.environ.setdefault("VECTOR_STORE_BACKEND", "memory")
os.environ.setdefault("ENABLE_LED", "false")
os.environ.setdefault("ALLOW_HASHING_FALLBACK", "true")
os.environ.setdefault("LLM_BASE_URL", "")
os.environ.setdefault("LLM_API_KEY", "")
os.environ["GEMINI_API_KEY"] = ""
os.environ.setdefault("LLM_FALLBACK_BASE_URL", "")
os.environ.setdefault("LLM_FALLBACK_API_KEY", "")
os.environ.setdefault("LLM_FALLBACK_MODEL", "")

import pytest

from embeddings import BgeM3Embedder, set_embedder
from retrieval import invalidate_lexical_index
from vector_store import MemoryVectorStore, set_vector_store


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Fresh storage dir, vector store, embedder and BM25 cache for every test."""
    monkeypatch.setenv("PAPER_STORAGE_DIR", str(tmp_path / "papers"))
    set_vector_store(MemoryVectorStore())
    set_embedder(BgeM3Embedder(dimensions=256, force_hashing=True))
    invalidate_lexical_index()
    from ingestion import jobs as jobs_module

    jobs_module.jobs._jobs.clear()
    yield
    set_vector_store(None)
    set_embedder(None)


@pytest.fixture
def paper_a(tmp_path):
    from pdf_processing.pipeline import process_paper
    from tests.helpers import PAPER_A, make_pdf

    return process_paper(make_pdf(tmp_path / "a.pdf", PAPER_A), "P001", chunk_size=300, overlap=50, filename="a.pdf")


@pytest.fixture
def paper_b(tmp_path):
    from pdf_processing.pipeline import process_paper
    from tests.helpers import PAPER_B, make_pdf

    return process_paper(make_pdf(tmp_path / "b.pdf", PAPER_B), "P002", chunk_size=300, overlap=50, filename="b.pdf")
