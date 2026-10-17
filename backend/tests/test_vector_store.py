import json
import os

import numpy as np
import pytest

from config import settings
from errors import VectorStoreUnavailable
from vector_store import MemoryVectorStore, RedisVectorStore, create_vector_store
from vector_store.redis_store import escape_tag


def chunk(i, paper="P1", section="RESULTS", text="text"):
    return {"paper_id": paper, "chunk_id": f"{paper}_{section}_{i:03d}", "section_name": section, "page_start": 1, "page_end": 2, "text": text, "title": "T", "filename": "f.pdf", "chunk_index": i}


def test_memory_store_search_filters_and_dedupes():
    store = MemoryVectorStore()
    store.upsert_chunks([chunk(1), chunk(2, paper="P2")], [[1, 0, 0], [0, 1, 0]])
    store.upsert_chunks([chunk(1)], [[1, 0, 0]])  # same id -> replaced, not duplicated
    assert store.count() == 2
    assert store.search([1, 0, 0], 5)[0]["chunk_id"] == "P1_RESULTS_001"
    assert [h["paper_id"] for h in store.search([0, 1, 0], 5, paper_ids=["P2"])] == ["P2"]
    assert store.search([1, 0, 0], 5, section_names=["METHODOLOGY"]) == []
    assert store.delete_paper("P1") == 1 and store.count() == 1
    with pytest.raises(VectorStoreUnavailable):
        store.search([1, 0], 3)


# ---------------------------------------------------------------- Redis protocol (fake server)
class FakePipeline:
    def __init__(self, client):
        self.client, self.ops = client, []

    def hset(self, key, mapping):
        self.ops.append((key, mapping))

    def execute(self):
        for key, mapping in self.ops:
            self.client.hashes[key.encode()] = {k.encode(): (v if isinstance(v, bytes) else str(v).encode()) for k, v in mapping.items()}


class FakeRedis:
    """Implements the handful of commands used by RedisVectorStore, including a tiny FT.SEARCH."""

    def __init__(self, redisearch=True, dim_hint=None):
        self.hashes, self.kv, self.commands, self.indexes, self.redisearch = {}, {}, [], set(), redisearch

    def ping(self):
        return True

    def execute_command(self, *args):
        self.commands.append(args)
        name = args[0]
        if name.startswith("FT.") and not self.redisearch:
            raise RuntimeError("unknown command 'FT._LIST', with args beginning with:")
        if name == "FT._LIST":
            return [i.encode() for i in self.indexes]
        if name == "FT.CREATE":
            self.indexes.add(args[1])
            return b"OK"
        if name == "FT.DROPINDEX":
            self.indexes.discard(args[1])
            return b"OK"
        if name == "FT.SEARCH":
            return self._search(args)
        raise AssertionError(f"unexpected {name}")

    def _search(self, args):
        blob = args[args.index("vec") + 1]
        query = np.frombuffer(blob, dtype=np.float32)
        limit = int(args[args.index("LIMIT") + 2])
        rows = []
        for key, fields in self.hashes.items():
            vec = np.frombuffer(fields[b"embedding"], dtype=np.float32)
            dist = 1 - float(vec @ query / (np.linalg.norm(vec) * np.linalg.norm(query)))
            rows.append((dist, key, fields))
        rows.sort(key=lambda r: r[0])
        reply = [len(rows)]
        for dist, key, fields in rows[:limit]:
            flat = [b"vector_score", str(dist).encode()]
            for k, v in fields.items():
                if k != b"embedding":
                    flat += [k, v]
            reply += [key, flat]
        return reply

    def get(self, key):
        return self.kv.get(key)

    def set(self, key, value):
        self.kv[key] = value.encode() if isinstance(value, str) else value

    def delete(self, *keys):
        for key in keys:
            self.hashes.pop(key, None)
            self.kv.pop(key, None)

    def pipeline(self, transaction=False):
        return FakePipeline(self)

    def scan_iter(self, match=None, count=None):
        prefix = match.rstrip("*").encode()
        return [k for k in list(self.hashes) if k.startswith(prefix)]

    def hget(self, key, field):
        return self.hashes[key].get(field.encode())

    def hgetall(self, key):
        return self.hashes[key]

    def config_get(self, name):
        return {b"appendonly": b"yes"}


def make_store(**kw):
    return RedisVectorStore(url="redis://fake", index_name="paper_chunks", client=FakeRedis(**kw))


def test_index_creation_arguments(monkeypatch):
    store = make_store()
    monkeypatch.setattr(settings, "redis_index_algorithm", "HNSW")
    store.ensure_index(1024)
    create = next(c for c in store.client.commands if c[0] == "FT.CREATE")
    assert create[2:6] == ("ON", "HASH", "PREFIX", 1)
    i = create.index("VECTOR")
    assert create[i + 1] == "HNSW" and create[i + 2] == 10 and "DIM" in create and 1024 in create and "COSINE" in create
    assert json.loads(store.client.kv["paper_chunks:meta"])["dimension"] == 1024
    store.ensure_index(1024)  # idempotent: no second FT.CREATE
    assert sum(1 for c in store.client.commands if c[0] == "FT.CREATE") == 1


def test_flat_index_has_no_hnsw_params(monkeypatch):
    monkeypatch.setattr(settings, "redis_index_algorithm", "FLAT")
    store = make_store()
    store.ensure_index(8)
    create = next(c for c in store.client.commands if c[0] == "FT.CREATE")
    assert create[create.index("VECTOR") + 1:create.index("VECTOR") + 3] == ("FLAT", 6)


def test_dimension_mismatch_requires_reindex():
    store = make_store()
    store.ensure_index(384)
    with pytest.raises(VectorStoreUnavailable, match="384-d"):
        store.ensure_index(1024)


def test_knn_query_string_and_tag_escaping():
    store = make_store()
    q = store.build_query(8, ["P-1", "P002"], ["RESULTS"])
    assert q == "(@paper_id:{P\\-1|P002} @section_name:{RESULTS})=>[KNN 8 @embedding $vec AS vector_score]"
    assert store.build_query(3, None, None) == "*=>[KNN 3 @embedding $vec AS vector_score]"
    assert escape_tag("a-b.c") == "a\\-b\\.c"


def test_upsert_search_roundtrip_and_idempotency():
    store = make_store()
    vectors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    store.upsert_chunks([chunk(1, text="alpha"), chunk(2, text="beta")], vectors)
    store.upsert_chunks([chunk(1, text="alpha")], [vectors[0]])
    assert store.count() == 2
    hits = store.search([0.9, 0.1, 0.0], 5)
    assert hits[0]["chunk_id"] == "P1_RESULTS_001" and hits[0]["text"] == "alpha"
    assert 0.9 < hits[0]["score"] <= 1.0 and isinstance(hits[0]["page_start"], int)
    assert {c["chunk_id"] for c in store.all_chunks()} == {"P1_RESULTS_001", "P1_RESULTS_002"}


def test_delete_paper_does_not_touch_prefix_lookalikes():
    store = make_store()
    store.upsert_chunks([chunk(1, paper="P_1"), chunk(1, paper="P_1_x")], [[1.0, 0], [0, 1.0]])
    assert store.delete_paper("P_1") == 1
    assert store.count("P_1_x") == 1


def test_plain_redis_without_redisearch_gives_actionable_error():
    with pytest.raises(VectorStoreUnavailable, match="RediSearch"):
        make_store(redisearch=False).verify()


def test_connection_failure_message():
    class Down(FakeRedis):
        def ping(self):
            raise ConnectionError("refused")

    with pytest.raises(VectorStoreUnavailable, match="Cannot connect to Redis"):
        RedisVectorStore(client=Down()).verify()
    health = RedisVectorStore(client=Down()).health()
    assert health["connected"] is False and "Cannot connect" in health["error"]


def test_factory_modes(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/0")
    monkeypatch.setattr(settings, "vector_store_backend", "redis")
    with pytest.raises(VectorStoreUnavailable):
        create_vector_store()
    monkeypatch.setattr(settings, "vector_store_backend", "auto")
    fallback = create_vector_store()
    assert fallback.backend == "memory" and fallback.degraded_reason  # reported, never silent
    monkeypatch.setattr(settings, "vector_store_backend", "memory")
    assert create_vector_store().persistent is False


@pytest.mark.redis
@pytest.mark.skipif(not os.getenv("REDIS_TEST_URL"), reason="REDIS_TEST_URL not set")
def test_against_real_redis_server():
    """Runs against a real server. With plain Redis this checks the missing-module path; with Redis Stack the full KNN path."""
    store = RedisVectorStore(url=os.environ["REDIS_TEST_URL"], index_name="paperintel_test")
    try:
        store.verify()
    except VectorStoreUnavailable as exc:
        assert "RediSearch" in exc.public_message  # plain Redis: clear error, not a crash
        return
    store.reset_index()
    store.upsert_chunks([chunk(1, text="alpha"), chunk(2, text="beta")], [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    assert store.search([1.0, 0.0, 0.0], 1)[0]["chunk_id"] == "P1_RESULTS_001"
    store.reset_index()
