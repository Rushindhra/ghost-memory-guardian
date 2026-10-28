"""Loads / removes the bundled SYNTHETIC demo archive (clearly flagged ``is_demo``)."""
from __future__ import annotations

import json
import sqlite3
import uuid

from ..core.config import REPO_ROOT
from ..schemas.schemas import MemoryIn
from . import memory_service as ms

DEMO_FILE = REPO_ROOT / "demo" / "synthetic_archive.json"


def load_demo(conn: sqlite3.Connection, retriever) -> dict[str, int]:
    data = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
    added = 0
    for m in data["memories"]:
        if conn.execute("SELECT 1 FROM memories WHERE id=?", (m["id"],)).fetchone():
            continue
        payload = MemoryIn(title=m["title"], body=m["body"], memory_date=m["memory_date"], category=m["category"],
                           people=m["people"], tags=m["tags"])
        ms.create_memory(conn, payload, source="demo", is_demo=True, memory_id=m["id"])
        retriever.index_memory(conn, m["id"])
        added += 1
    docs = 0
    if conn.execute("SELECT COUNT(*) FROM life_docs WHERE is_demo=1").fetchone()[0] == 0:
        for d in data["life_documents"]:
            ts = ms.now_iso()
            conn.execute("INSERT INTO life_docs(id,title,kind,notes,expiry_date,remind_date,is_demo,created_at,updated_at)"
                         " VALUES(?,?,?,?,?,?,1,?,?)", (uuid.uuid4().hex, d["title"], d["kind"], d["notes"],
                                                       d["expiry_date"], d["remind_date"], ts, ts))
            docs += 1
    if conn.execute("SELECT COUNT(*) FROM transcripts WHERE is_demo=1").fetchone()[0] == 0:
        for t in data["transcripts"]:
            ts = ms.now_iso()
            conn.execute("INSERT INTO transcripts(id,stored_name,original_name,mime,size,sha256,title,language,text,"
                         "engine,status,is_demo,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
                         (uuid.uuid4().hex, "", "demo-text-only", "text/plain", 0, "", t["title"], t["language"],
                          t["text"], "demo-text", "draft", ts, ts))
    conn.commit()
    return {"memories_added": added, "life_documents_added": docs}


def remove_demo(conn: sqlite3.Connection, retriever, files) -> dict[str, int]:
    ids = [r[0] for r in conn.execute("SELECT id FROM memories WHERE is_demo=1")]
    removed_files = 0
    for mid in ids:
        retriever.remove_memory(conn, mid)
        removed_files += sum(files.delete(n) for n in ms.delete_memory(conn, mid))
    for r in conn.execute("SELECT stored_name FROM transcripts WHERE is_demo=1 AND stored_name!=''").fetchall():
        files.delete(r[0])
    conn.execute("DELETE FROM transcripts WHERE is_demo=1")
    conn.execute("DELETE FROM life_docs WHERE is_demo=1")
    conn.commit()
    return {"memories_removed": len(ids), "files_removed": removed_files}
