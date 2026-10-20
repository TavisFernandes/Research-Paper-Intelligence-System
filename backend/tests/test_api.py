import pytest
from fastapi.testclient import TestClient

from api.app import app
from tests.helpers import PAPER_A, PAPER_B, make_blank_pdf, make_encrypted_pdf, make_pdf


@pytest.fixture
def client():
    return TestClient(app)


def upload(client, path, name=None):
    with open(path, "rb") as fh:
        return client.post("/api/papers/upload", files=[("files", (name or path.name, fh.read(), "application/pdf"))])


@pytest.fixture
def two_papers(client, tmp_path):
    ids = []
    for pages, name in ((PAPER_A, "a.pdf"), (PAPER_B, "b.pdf")):
        r = upload(client, make_pdf(tmp_path / name, pages))
        assert r.status_code == 202, r.text
        job = r.json()["jobs"][0]
        assert client.get(f"/api/ingestion/{job['job_id']}").json()["status"] == "completed"
        ids.append(job["paper_id"])
    return ids


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] in {"ok", "degraded"} and body["components"]["vector_store"]["backend"] == "memory"
    assert "api_key" not in str(body).lower() or body["components"]["llm"]["api_key_set"] in (True, False)
    assert any("memory" in w.lower() or "In-memory" in w for w in body["warnings"])


def test_upload_status_list_and_get(client, tmp_path):
    r = upload(client, make_pdf(tmp_path / "a.pdf"))
    job = r.json()["jobs"][0]
    assert job["paper_id"] == "P001"
    done = client.get(f"/api/ingestion/{job['job_id']}").json()
    assert done["status"] == "completed" and done["progress"] == 100
    assert client.get("/api/papers/P001/status").json()["status"] == "completed"
    listing = client.get("/api/papers").json()
    assert listing[0]["paper_id"] == "P001" and listing[0]["title"] and "ABSTRACT" in listing[0]["sections"] and listing[0]["indexing"]["indexed"]
    paper = client.get("/api/papers/P001").json()
    assert paper["pages"][0]["extraction_method"] == "text" and paper["chunks"][0]["chunk_id"]


def test_duplicate_upload_is_not_reingested(client, tmp_path):
    path = make_pdf(tmp_path / "a.pdf")
    first = upload(client, path).json()["jobs"][0]
    second = upload(client, path, name="renamed.pdf").json()["jobs"][0]
    assert second["status"] == "duplicate" and second["duplicate_of"] == first["paper_id"]
    assert len(client.get("/api/papers").json()) == 1


def test_multiple_files_in_one_request(client, tmp_path):
    a, b = make_pdf(tmp_path / "a.pdf", PAPER_A), make_pdf(tmp_path / "b.pdf", PAPER_B)
    r = client.post("/api/papers/upload", files=[("files", ("a.pdf", a.read_bytes(), "application/pdf")), ("files", ("b.pdf", b.read_bytes(), "application/pdf")),
                                                  ("files", ("notes.txt", b"hello", "text/plain"))])
    body = r.json()
    assert r.status_code == 202 and [j["paper_id"] for j in body["jobs"]] == ["P001", "P002"]
    assert body["rejected"][0]["filename"] == "notes.txt"


@pytest.mark.parametrize("name,content,expected", [("x.txt", b"hello", "Only PDF"), ("x.pdf", b"", "empty"), ("x.pdf", b"hello world", "does not look like a PDF")])
def test_invalid_uploads_rejected_with_400(client, name, content, expected):
    r = client.post("/api/papers/upload", files=[("files", (name, content, "application/pdf"))])
    assert r.status_code == 400 and expected in r.json()["detail"]


def test_corrupt_encrypted_and_blank_pdfs_fail_gracefully(client, tmp_path):
    cases = {"corrupt.pdf": b"%PDF-1.4\nthis is not a real pdf body", "enc.pdf": make_encrypted_pdf(tmp_path / "e.pdf").read_bytes(),
             "blank.pdf": make_blank_pdf(tmp_path / "b.pdf").read_bytes()}
    for name, content in cases.items():
        r = client.post("/api/papers/upload", files=[("files", (name, content, "application/pdf"))])
        job = client.get(f"/api/ingestion/{r.json()['jobs'][0]['job_id']}").json()
        assert job["status"] == "failed" and job["error"], name
        assert "Traceback" not in job["error"] and "/" not in job["error"].replace("/or", "")
    assert client.get("/api/papers").json() == []  # nothing half-stored


def test_unknown_and_malicious_ids(client):
    assert client.get("/api/papers/P404").status_code == 404
    assert client.get("/api/papers/..%2Fsecret").status_code in (400, 404)
    assert client.get("/api/ingestion/nope").status_code == 404
    assert client.delete("/api/papers/P404").status_code == 404


def test_search_endpoint(client, two_papers):
    r = client.post("/api/search", json={"query": "hard negatives mined using BM25", "top_k": 3})
    body = r.json()
    assert r.status_code == 200 and body["results"][0]["paper_id"] == "P001" and body["results"][0]["section_name"] == "METHODOLOGY"
    assert client.post("/api/search", json={"query": "quantum chromodynamics lattice"}).json()["results"] == []
    assert client.post("/api/search", json={"query": "x", "paper_ids": ["P999"]}).status_code == 404
    bad = client.post("/api/search", json={"query": "   "})
    assert bad.status_code == 422 and bad.json()["detail"] == "Invalid request."
    assert client.post("/api/search", json={"query": "x", "top_k": 0}).status_code == 422
    assert client.post("/api/search", json={"query": "x", "mode": "weird"}).status_code == 422


def test_qa_without_llm_returns_evidence_only(client, two_papers):
    body = client.post("/api/qa", json={"query": "Which dataset was used for training?"}).json()
    assert body["status"] == "evidence_only" and body["answer"] is None and body["evidence"]
    none = client.post("/api/qa", json={"query": "quantum chromodynamics lattice"}).json()
    assert none["status"] == "insufficient_evidence"


def test_qa_reuses_only_matching_cached_retrieval(client, two_papers):
    search = client.post("/api/search", json={"query": "hard negatives mined using BM25", "top_k": 1}).json()
    hit = search["results"][0]
    payload = {
        "query": "hard negatives mined using BM25",
        "paper_ids": two_papers,
        "top_k": 1,
        "retrieval_id": search["retrieval_id"],
    }
    response = client.post("/api/qa", json=payload)
    assert response.status_code == 200 and response.json()["evidence"][0]["text"] == hit["text"]
    assert response.json()["retrieval"]["mode"] == "hybrid"
    # A mismatched token is ignored; the normal query is re-run, never trusted as arbitrary evidence.
    mismatched_search = client.post("/api/search", json={"query": "hard negatives mined using BM25", "top_k": 1}).json()
    payload.update({"query": "quantum chromodynamics", "retrieval_id": mismatched_search["retrieval_id"]})
    assert client.post("/api/qa", json=payload).json()["evidence"] == []


def test_summaries(client, two_papers):
    body = client.post("/api/summarize", json={"paper_id": "P001"}).json()
    assert body["summary"] and body["sections"]
    sec = client.post("/api/summarize", json={"paper_id": "P001", "section_name": "RESULTS"}).json()
    assert sec["found"] and "0.91" in sec["summary"]
    assert client.post("/api/summarize", json={"paper_id": "P404"}).status_code == 404


def test_compare_and_insights(client, two_papers):
    r = client.post("/api/compare", json={"paper_ids": two_papers})
    assert r.status_code == 200 and len(r.json()["table"]) == 10
    assert client.post("/api/compare", json={"paper_ids": ["P001", "P001"]}).status_code == 400
    assert client.post("/api/compare", json={"paper_ids": ["P001"]}).status_code == 422
    assert client.post("/api/compare", json={"paper_ids": ["P001", "P777"]}).status_code == 404
    ins = client.post("/api/insights", json={"paper_ids": two_papers})
    assert ins.status_code == 200 and ins.json()["paper_count"] == 2
    assert client.post("/api/insights", json={"paper_ids": ["P001"]}).status_code == 422
    assert client.post("/api/insights", json={"paper_ids": ["P001"] * 101}).status_code == 422


def test_evaluation_endpoints(client, two_papers):
    chunk_id = client.post("/api/search", json={"query": "hard negatives mined using BM25", "top_k": 1}).json()["results"][0]["chunk_id"]
    r = client.post("/api/evaluate/retrieval", json={"queries": [{"query": "hard negatives mined using BM25", "relevant_chunk_ids": [chunk_id]},
                                                                  {"query": "CIFAR-10 accuracy", "relevant_paper_ids": ["P002"]}]})
    assert r.status_code == 200 and set(r.json()["metrics"]) >= {"recall@5", "recall@10", "mrr@10", "ndcg@10"} and r.json()["metrics"]["mrr@10"] > 0.5
    assert client.post("/api/evaluate/retrieval", json={"queries": [{"query": "x"}]}).status_code == 400
    ok = client.post("/api/evaluate/summarization", json={"predictions": ["a cat sat"], "references": ["a cat sat down"]})
    assert ok.status_code == 200 and ok.json()["metrics"]["rouge1"] > 0.5
    assert client.post("/api/evaluate/summarization", json={}).status_code == 400
    assert client.post("/api/evaluate/summarization", json={"predictions": ["x"], "references": [""]}).status_code == 400
    gen = client.post("/api/evaluate/summarization", json={"paper_id": "P001", "reference_summary": "We fine-tune BGE-M3 on PubMedQA."})
    assert gen.status_code == 200 and gen.json()["source"] == "generated_summary"


def test_delete_removes_vectors_and_files(client, two_papers):
    assert client.delete("/api/papers/P001").json()["chunks_removed"] > 0
    assert client.get("/api/papers/P001").status_code == 404
    assert all(r["paper_id"] != "P001" for r in client.post("/api/search", json={"query": "BM25 negatives"}).json()["results"])


def test_reindex_paper(client, two_papers):
    assert client.post("/api/papers/P001/reindex").json()["indexing"]["indexed"] is True
    assert client.post("/api/reindex", json={"reset": False}).json()["reindexed"] == 2


def test_unexpected_errors_do_not_leak_internals(client, monkeypatch):
    import sys

    app_module = sys.modules["api.app"]

    monkeypatch.setattr(app_module, "list_papers", lambda: (_ for _ in ()).throw(RuntimeError("secret /etc/path password=hunter2")))
    safe = TestClient(app, raise_server_exceptions=False)
    r = safe.get("/api/papers")
    assert r.status_code == 500 and r.json() == {"detail": "Internal server error."}


def test_redis_down_surfaces_503(client, two_papers, monkeypatch):
    from errors import VectorStoreUnavailable
    from vector_store import MemoryVectorStore, set_vector_store

    class Broken(MemoryVectorStore):
        def search(self, *a, **k):
            raise VectorStoreUnavailable("Cannot connect to Redis. Start it with `docker compose up -d redis` and check REDIS_URL.")

    set_vector_store(Broken())
    r = client.post("/api/search", json={"query": "BM25 negatives", "mode": "dense"})
    assert r.status_code == 503 and "Redis" in r.json()["detail"]
