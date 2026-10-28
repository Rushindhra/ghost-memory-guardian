import sqlite3

import numpy as np

from app.services.llm_service import (NOT_FOUND_ANSWER, LLMUnavailable, ungrounded_terms, validate_citations)
from app.services.retrieval_service import chunk_text
from conftest import mem


def search(client, q, **kw):
    return client.post("/api/search", json={"query": q, **kw}).json()


def test_chunking_respects_size_and_keeps_text():
    text = ("First paragraph. " * 20) + "\n\n" + ("Second paragraph sentence. " * 80)
    chunks = chunk_text(text, size=300, overlap=40)
    assert all(len(c) <= 330 for c in chunks) and len(chunks) > 4
    assert chunk_text("") == [] and chunk_text("short") == ["short"]


def test_semantic_search_finds_the_right_memory(demo):
    r = search(demo, "who taught Lily to knead bread dough", ask=False)
    assert r["results"][0]["memory"]["id"] == "demo-001"
    assert r["results"][0]["confidence"] in ("high", "medium") and r["results"][0]["excerpts"]


def test_multilingual_keyword_match(demo):
    assert search(demo, "arroz con leche canela", ask=False)["results"][0]["memory"]["id"] == "demo-006"


def test_unsupported_question_is_rejected_without_calling_llm(demo, llm):
    r = search(demo, "What is the capital of Australia?")
    assert r["supported"] is False and r["answer"]["status"] == "not_found"
    assert r["answer"]["text"] == NOT_FOUND_ANSWER and llm.calls == []


def test_answer_with_valid_citations(demo, llm):
    llm.reply = "Rosa taught Lily to knead cinnamon bread dough [1]."
    r = search(demo, "who taught Lily to knead bread dough")
    a = r["answer"]
    assert a["status"] == "answered" and a["citations"][0]["memory_id"] == "demo-001"
    assert a["citations"][0]["excerpt"]
    assert llm.calls and "SOURCES:" in llm.calls[0][1]["content"]


def test_invalid_citations_are_stripped(demo, llm):
    llm.reply = "Rosa baked cinnamon bread [1]. It was lovely [9]."
    a = search(demo, "who baked cinnamon bread")["answer"]
    assert "[9]" not in a["text"] and all(c["n"] != 9 for c in a["citations"])
    assert any("Removed 1 citation" in w for w in a["warnings"])


def test_uncited_answer_is_discarded(demo, llm):
    llm.reply = "Rosa baked bread on Sundays."
    a = search(demo, "who baked cinnamon bread")["answer"]
    assert a["status"] == "not_found" and a["citations"] == []
    assert any("cited no source" in w for w in a["warnings"])


def test_ungrounded_names_are_flagged(demo, llm):
    llm.reply = "Rosa baked bread with Napoleon in 1812 [1]."
    a = search(demo, "who baked cinnamon bread")["answer"]
    joined = " ".join(a["warnings"])
    assert "Napoleon" in joined and "1812" in joined


def test_llm_unavailable_never_fabricates(demo, llm):
    llm.reply = LLMUnavailable("Ollama is not running. Install it and run: ollama pull qwen3:4b")
    r = search(demo, "who taught Lily to knead bread dough")
    assert r["answer"]["status"] == "ai_unavailable" and r["answer"]["text"] is None
    assert "ollama pull" in r["answer"]["message"] and r["results"]  # retrieval still works


def test_model_says_not_found(demo, llm):
    llm.reply = NOT_FOUND_ANSWER
    assert search(demo, "who baked cinnamon bread")["answer"]["status"] == "not_found"


def test_helpers():
    clean, cited, removed = validate_citations("A [2] and B [7] and C [2].", {1, 2})
    assert cited == [2] and removed == [7] and "[7]" not in clean
    assert ungrounded_terms("Born in 1950 in Paris.", "born in 1950") == ["Paris"]


def test_edit_and_delete_update_index(client):
    a = client.post("/api/memories", json=mem("Boat", "The yellow submarine sailed.")).json()
    assert search(client, "yellow submarine", ask=False)["results"][0]["memory"]["id"] == a["id"]
    client.put(f"/api/memories/{a['id']}", json=mem("Boat", "A red balloon floated away."))
    assert search(client, "yellow submarine", ask=False)["supported"] is False
    assert search(client, "red balloon", ask=False)["results"][0]["memory"]["id"] == a["id"]
    client.delete(f"/api/memories/{a['id']}")
    assert search(client, "red balloon", ask=False)["results"] == []


def test_index_rebuilds_after_corruption(settings, ctx):
    from app.core.context import build_context
    from app.main import create_app
    from fastapi.testclient import TestClient
    app = create_app(settings, ctx)
    with TestClient(app) as c:
        c.post("/api/memories", json=mem("Corrupt me", "Unique marmalade jar story."))
    (settings.index_dir / "chunks.faiss").write_bytes(b"garbage")
    ctx2 = build_context(settings, llm=ctx.llm, transcriber=ctx.transcriber)  # must not crash
    assert "rebuilt" in ctx2.retriever.index_status
    with TestClient(create_app(settings, ctx2)) as c:
        assert search(c, "marmalade jar", ask=False)["results"]


def test_reindex_endpoint_and_vector_blob_roundtrip(demo, settings):
    out = demo.post("/api/system/reindex").json()
    assert out["chunks"] >= 14
    conn = sqlite3.connect(settings.db_path)
    blob = conn.execute("SELECT embedding FROM chunks LIMIT 1").fetchone()[0]
    v = np.frombuffer(blob, dtype=np.float32)
    assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-3  # normalised, stored as raw float32 (no pickle)


def test_related_memories(demo):
    ids = [i["id"] for i in demo.get("/api/memories/demo-001/related").json()["items"]]
    assert "demo-001" not in ids and ids  # shares people / content with others


def test_family_summary_uses_only_selected_records(demo, llm):
    llm.reply = "Elias worked at the railway yard [1] and retired in 1989 [2]."
    r = demo.post("/api/timeline/summary", json={"memory_ids": ["demo-003", "demo-010"]})
    assert r.status_code == 200 and r.json()["cited"] == [1, 2]
    prompt = llm.calls[-1][1]["content"]
    assert "railway" in prompt and "cinnamon" not in prompt
    assert demo.post("/api/timeline/summary", json={"memory_ids": ["ghost"]}).status_code == 404
    llm.reply = LLMUnavailable("no ollama")
    assert demo.post("/api/timeline/summary", json={"memory_ids": ["demo-003"]}).status_code == 503


def test_ghost_mode_separates_facts_from_fiction_and_leaves_archive_untouched(demo, llm):
    before = demo.get("/api/memories/demo-012").json()
    llm.reply = ('{"title":"The Lantern","story":"Rosa lit candles [1]. A pale lantern drifted down the hall.",'
                 '"invented_elements":["pale lantern drifting"]}')
    r = demo.post("/api/ghost/generate", json={"memory_ids": ["demo-012"], "intensity": "spooky"}).json()
    assert r["fiction"] is True and r["invented_elements"] == ["pale lantern drifting"]
    assert r["verified_facts"][0]["memory_id"] == "demo-012" and "Verified facts" in r["notice"]
    assert "spooky" in llm.calls[-1][0]["content"].lower()
    assert demo.get("/api/memories/demo-012").json() == before  # archive unchanged


def test_ghost_remembrance_prompt_and_bad_json(demo, llm):
    llm.reply = "Just plain text, not JSON."
    r = demo.post("/api/ghost/generate", json={"memory_ids": ["demo-001"], "intensity": "remembrance"}).json()
    assert r["warnings"] and r["invented_elements"] == []
    assert "NO horror" in llm.calls[-1][0]["content"]
    assert demo.post("/api/ghost/generate", json={"memory_ids": ["demo-001"], "intensity": "gore"}).status_code == 422
    assert demo.post("/api/ghost/generate", json={"memory_ids": []}).status_code == 422


def test_non_loopback_ollama_is_refused_by_default():
    """Memories must never be sent to a non-local LLM unless the owner explicitly opts in."""
    import pytest
    from app.services.llm_service import LLMUnavailable, OllamaClient

    client = OllamaClient("http://192.0.2.10:11434", "qwen3:4b", 5, 0.2, allow_remote=False, loopback=False)
    st = client.status()
    assert st["reachable"] is False and "not on this computer" in st["message"]
    with pytest.raises(LLMUnavailable):
        client.chat([{"role": "user", "content": "private text"}])
