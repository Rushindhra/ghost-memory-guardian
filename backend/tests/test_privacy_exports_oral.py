import io
import json
import socket
import zipfile

import pytest

from app.services import export_service
from conftest import PNG, make_wav, mem


# ------------------------------------------------------------ exports ----
def test_json_and_markdown_export(demo):
    j = demo.get("/api/export/json").json()
    assert j["format"] == "ghost-export" and len(j["memories"]) == 14 and j["life_documents"]
    md = demo.get("/api/export/markdown").text
    assert "Grandma Rosa's Sunday cinnamon bread" in md and "synthetic demo data" in md


def test_backup_and_restore_roundtrip(client, ctx, tmp_path):
    m = client.post("/api/memories", json=mem("Keep me", "important")).json()
    client.post(f"/api/memories/{m['id']}/attachments", files={"file": ("p.png", PNG, "image/png")})
    blob = client.get("/api/export/backup").content
    zpath = tmp_path / "b.zip"
    zpath.write_bytes(blob)
    target = tmp_path / "restored"
    assert export_service.restore_backup(zpath, target)["restored_entries"] == 2
    import sqlite3
    row = sqlite3.connect(target / "ghost.sqlite3").execute("SELECT title FROM memories").fetchone()
    assert row[0] == "Keep me" and len(list((target / "files").iterdir())) == 1
    with pytest.raises(export_service.RestoreError):  # never overwrite an existing database
        export_service.restore_backup(zpath, target)


def test_restore_rejects_zip_slip(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("manifest.json", json.dumps({"format": "ghost-backup", "version": 1}))
        z.writestr("files/../../escape.txt", "x")
    with pytest.raises(export_service.RestoreError):
        export_service.restore_backup(bad, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()
    junk = tmp_path / "junk.zip"
    junk.write_bytes(b"not a zip")
    with pytest.raises(export_service.RestoreError):
        export_service.restore_backup(junk, tmp_path / "out2")


# ------------------------------------------------------ life documents ----
def test_life_docs_search_and_ics(client):
    r = client.post("/api/life-docs", json={"title": "Car warranty", "kind": "warranty", "notes": "Call, then; email",
                                            "expiry_date": "2027-03-01", "remind_date": "2027-02-01"})
    assert r.status_code == 201
    client.post("/api/life-docs", json={"title": "Soup recipe", "kind": "recipe", "notes": "lentils"})
    assert [d["title"] for d in client.get("/api/life-docs", params={"q": "2027-03"}).json()["items"]] == ["Car warranty"]
    assert "legal, medical" in client.get("/api/life-docs").json()["disclaimer"]
    ics = client.get("/api/life-docs/export.ics")
    body = ics.text
    assert ics.headers["content-type"].startswith("text/calendar")
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.count("BEGIN:VEVENT") == 2
    assert "DTSTART;VALUE=DATE:20270201" in body and "Call\\, then\\; email" in body and body.endswith("END:VCALENDAR\r\n")
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    soup = [d for d in client.get("/api/life-docs").json()["items"] if d["kind"] == "recipe"][0]
    assert client.get(f"/api/life-docs/{soup['id']}/ics").status_code == 400  # nothing dated to export
    assert client.post("/api/life-docs", json={"title": "x", "expiry_date": "03/01/2027"}).status_code == 422
    assert client.delete(f"/api/life-docs/{soup['id']}").status_code == 200


# ----------------------------------------------------------- the lock ----
def test_passphrase_lock_flow(client):
    assert client.get("/api/privacy/lock-status").json() == {"enabled": False, "unlocked": True}
    assert client.post("/api/privacy/lock/enable", json={"passphrase": "short"}).status_code == 422
    assert client.post("/api/privacy/lock/enable", json={"passphrase": "correct horse battery"}).status_code == 200
    assert client.get("/api/memories").status_code == 200  # the enabling browser stays unlocked
    client.post("/api/privacy/logout")
    assert client.get("/api/memories").status_code == 401 and client.get("/api/export/json").status_code == 401
    assert client.get("/api/system/health").status_code == 200  # status only, no memory content
    assert client.post("/api/privacy/unlock", json={"passphrase": "wrong"}).status_code == 401
    assert client.post("/api/privacy/unlock", json={"passphrase": "correct horse battery"}).status_code == 200
    assert client.get("/api/memories").status_code == 200
    assert client.post("/api/privacy/lock/disable", json={"passphrase": "nope"}).status_code == 401
    assert client.post("/api/privacy/lock/disable", json={"passphrase": "correct horse battery"}).status_code == 200
    assert client.get("/api/privacy/lock-status").json()["enabled"] is False


def test_passphrase_is_hashed_and_bruteforce_throttled(client, settings):
    import sqlite3
    client.post("/api/privacy/lock/enable", json={"passphrase": "correct horse battery"})
    stored = sqlite3.connect(settings.db_path).execute("SELECT value FROM settings WHERE key='lock_hash'").fetchone()[0]
    assert stored.startswith("scrypt$") and "correct horse" not in stored
    client.post("/api/privacy/logout")
    codes = [client.post("/api/privacy/unlock", json={"passphrase": f"bad{i}"}).status_code for i in range(5)]
    assert 429 in codes
    assert client.post("/api/privacy/unlock", json={"passphrase": "correct horse battery"}).status_code == 429


def test_privacy_report_is_honest(client):
    r = client.get("/api/privacy/report").json()
    assert r["local_only"] and r["encryption_at_rest"] is False and "none" in r["telemetry"]
    assert "backups" in r["deletion_notice"] and "BitLocker" in r["encryption_recommendation"]


def test_storage_directory_validation(client, tmp_path, monkeypatch):
    from app.core import config
    monkeypatch.setattr(config, "BOOTSTRAP_FILE", tmp_path / "boot.json")
    assert client.post("/api/privacy/storage", json={"data_dir": "relative/path"}).status_code == 422
    r = client.post("/api/privacy/storage", json={"data_dir": str(tmp_path / "newdata")}).json()
    assert r["restart_required"] and json.loads((tmp_path / "boot.json").read_text())["data_dir"].endswith("newdata")


# ---------------------------------------------------- oral history ------
def test_oral_history_flow(client, ctx, stt):
    up = client.post("/api/oral", files={"file": ("grandpa.wav", make_wav(), "audio/wav")}, data={"language": "en"})
    assert up.status_code == 201
    t = up.json()["transcript"]
    assert t["text"].startswith("Hello") and t["engine"] == "fake-whisper" and "mistakes" in t["disclaimer"]
    edited = client.put(f"/api/oral/{t['id']}", json={"text": "Hello, corrected.", "title": "Grandpa"}).json()
    assert edited["text"] == "Hello, corrected." and edited["engine"].endswith("+edited")
    assert client.get(t["audio_url"]).status_code == 200
    m = client.post(f"/api/oral/{t['id']}/confirm", json={"title": "Grandpa talks", "memory_date": "2020", "people": ["Grandpa"]})
    assert m.status_code == 201 and m.json()["source"] == "oral_history" and m.json()["attachments"][0]["kind"] == "audio"
    assert client.post(f"/api/oral/{t['id']}/confirm", json={"title": "again"}).status_code == 409
    hit = client.post("/api/search", json={"query": "Hello corrected", "ask": False}).json()
    assert hit["results"][0]["memory"]["id"] == m.json()["id"]


def test_oral_works_without_whisper_model(client, stt):
    stt.available = False
    up = client.post("/api/oral", files={"file": ("a.wav", make_wav(), "audio/wav")}).json()
    assert up["message"] and up["transcript"]["text"] == ""  # recording is kept; user can type a transcript
    tid = up["transcript"]["id"]
    assert client.post(f"/api/oral/{tid}/transcribe", json={}).status_code == 503
    assert client.post(f"/api/oral/{tid}/confirm", json={"title": "x"}).status_code == 400  # empty text
    assert client.put(f"/api/oral/{tid}", json={"text": "typed by hand"}).json()["engine"] == "manual"
    assert client.post("/api/oral", files={"file": ("a.png", PNG, "image/png")}).status_code == 400  # not audio


def test_oral_delete_removes_audio_file(client, ctx):
    t = client.post("/api/oral", files={"file": ("a.wav", make_wav(), "audio/wav")}).json()["transcript"]
    assert len(list(ctx.settings.files_dir.iterdir())) == 1
    client.delete(f"/api/oral/{t['id']}")
    assert list(ctx.settings.files_dir.iterdir()) == []


# ------------------------------------------------------------ system ------
def test_health_reports_components_honestly(client, stt, llm):
    h = client.get("/api/system/health").json()
    assert h["backend"]["ok"] and h["database"]["schema_version"] == 1 and h["telemetry"] is False
    assert h["embeddings"]["neural"] is False and h["embeddings"]["mode"].startswith("keyword")
    assert h["offline"]["offline_ready"] is False  # lexical fallback => not fully offline-ready
    assert h["offline"]["core_archive_ready"] is True


def test_overview_numbers_are_live(client):
    assert client.get("/api/system/overview").json()["total_memories"] == 0
    client.post("/api/demo/load")
    o = client.get("/api/system/overview").json()
    assert o["total_memories"] == 14 and o["demo_memories"] == 14 and len(o["recent"]) == 5
    assert client.delete("/api/demo").json()["memories_removed"] == 14
    assert client.get("/api/system/overview").json()["total_memories"] == 0


def test_runtime_settings_validation(client, llm):
    assert client.put("/api/system/settings", json={"llm_model": "bad model; rm -rf /"}).status_code == 422
    assert client.put("/api/system/settings", json={"llm_model": "llama3.2:3b"}).json()["llm_model"] == "llama3.2:3b"


def test_untrusted_host_header_is_rejected(client):
    assert client.get("/api/ping", headers={"host": "evil.example"}).status_code == 400


# ---------------------------------------------------- offline proof ------
def test_full_flow_with_network_blocked(demo, monkeypatch):
    """Everything except the (faked) local LLM works while every non-loopback socket is refused."""
    real_connect = socket.socket.connect

    def guarded(self, address):
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1", "localhost"):
            raise OSError("network disabled for test")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    assert demo.post("/api/search", json={"query": "flood at Alder Creek", "ask": False}).status_code == 200
    assert demo.get("/api/export/backup").status_code == 200
    assert demo.post("/api/memories", json=mem("offline", "written without network")).status_code == 201
