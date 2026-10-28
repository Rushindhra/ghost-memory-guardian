"""Memory CRUD against SQLite.  Pure data access: no AI, no file I/O."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from ..schemas.schemas import MemoryIn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sort_key(memory_date: str | None) -> str | None:
    """Normalise partial dates so '1984' sorts as 1984-01-01."""
    if not memory_date:
        return None
    parts = memory_date.split("-")
    return "-".join([parts[0], parts[1] if len(parts) > 1 else "01", parts[2] if len(parts) > 2 else "01"])


class NotFound(LookupError):
    pass


def _hydrate(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    mid = row["id"]
    data = dict(row)
    data["is_demo"] = bool(data["is_demo"])
    data["people"] = [r["name"] for r in conn.execute(
        "SELECT name FROM memory_people WHERE memory_id=? ORDER BY name", (mid,))]
    data["tags"] = [r["tag"] for r in conn.execute(
        "SELECT tag FROM memory_tags WHERE memory_id=? ORDER BY tag", (mid,))]
    data["attachments"] = [dict(r) | {"url": f"/api/files/{r['id']}"} for r in conn.execute(
        "SELECT id, kind, original_name, mime, size, created_at, ocr_text IS NOT NULL AS has_ocr "
        "FROM attachments WHERE memory_id=? ORDER BY created_at", (mid,))]
    return data


def create_memory(conn: sqlite3.Connection, payload: MemoryIn, source: str = "manual",
                  is_demo: bool = False, memory_id: str | None = None) -> dict[str, Any]:
    mid, ts = memory_id or uuid.uuid4().hex, now_iso()
    conn.execute(
        "INSERT INTO memories(id,title,body,memory_date,sort_date,category,source,is_demo,created_at,updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (mid, payload.title, payload.body, payload.memory_date, sort_key(payload.memory_date),
         payload.category, source, int(is_demo), ts, ts),
    )
    _replace_links(conn, mid, payload)
    conn.commit()
    return get_memory(conn, mid)


def update_memory(conn: sqlite3.Connection, memory_id: str, payload: MemoryIn) -> dict[str, Any]:
    cur = conn.execute(
        "UPDATE memories SET title=?, body=?, memory_date=?, sort_date=?, category=?, updated_at=? WHERE id=?",
        (payload.title, payload.body, payload.memory_date, sort_key(payload.memory_date),
         payload.category, now_iso(), memory_id),
    )
    if cur.rowcount == 0:
        raise NotFound(memory_id)
    _replace_links(conn, memory_id, payload)
    conn.commit()
    return get_memory(conn, memory_id)


def _replace_links(conn: sqlite3.Connection, mid: str, payload: MemoryIn) -> None:
    conn.execute("DELETE FROM memory_people WHERE memory_id=?", (mid,))
    conn.execute("DELETE FROM memory_tags WHERE memory_id=?", (mid,))
    conn.executemany("INSERT INTO memory_people(memory_id,name) VALUES(?,?)", [(mid, p) for p in payload.people])
    conn.executemany("INSERT INTO memory_tags(memory_id,tag) VALUES(?,?)", [(mid, t) for t in payload.tags])


def get_memory(conn: sqlite3.Connection, memory_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
    if row is None:
        raise NotFound(memory_id)
    return _hydrate(conn, row)


def get_many(conn: sqlite3.Connection, ids: list[str]) -> list[dict[str, Any]]:
    """Fetch memories preserving the order of ``ids``; unknown ids raise NotFound."""
    return [get_memory(conn, i) for i in dict.fromkeys(ids)]


def list_memories(conn: sqlite3.Connection, q: str | None = None, person: str | None = None,
                  category: str | None = None, tag: str | None = None, date_from: str | None = None,
                  date_to: str | None = None, limit: int = 50, offset: int = 0,
                  order: str = "recent") -> dict[str, Any]:
    where, args = ["1=1"], []
    if q:
        like = f"%{q.strip()}%"
        where.append(
            "(m.title LIKE ? OR m.body LIKE ? OR EXISTS(SELECT 1 FROM memory_people p WHERE p.memory_id=m.id AND p.name LIKE ?) "
            "OR EXISTS(SELECT 1 FROM memory_tags t WHERE t.memory_id=m.id AND t.tag LIKE ?) "
            "OR EXISTS(SELECT 1 FROM attachments a WHERE a.memory_id=m.id AND a.ocr_text LIKE ?))")
        args += [like] * 5
    if person:
        where.append("EXISTS(SELECT 1 FROM memory_people p WHERE p.memory_id=m.id AND p.name=?)")
        args.append(person)
    if category:
        where.append("m.category=?")
        args.append(category)
    if tag:
        where.append("EXISTS(SELECT 1 FROM memory_tags t WHERE t.memory_id=m.id AND t.tag=?)")
        args.append(tag.lower())
    if date_from:
        where.append("m.sort_date >= ?")
        args.append(sort_key(date_from))
    if date_to:
        # inclusive of the whole year/month when a partial date is given
        end = date_to if date_to.count("-") == 2 else (date_to + "-31" if date_to.count("-") == 1 else date_to + "-12-31")
        where.append("m.sort_date <= ?")
        args.append(end)
    clause = " AND ".join(where)
    order_sql = {
        "recent": "m.created_at DESC",
        "oldest": "COALESCE(m.sort_date,'9999') ASC, m.created_at ASC",
        "newest": "COALESCE(m.sort_date,'0000') DESC, m.created_at DESC",
    }.get(order, "m.created_at DESC")
    total = conn.execute(f"SELECT COUNT(*) FROM memories m WHERE {clause}", args).fetchone()[0]
    rows = conn.execute(
        f"SELECT m.* FROM memories m WHERE {clause} ORDER BY {order_sql} LIMIT ? OFFSET ?",
        [*args, limit, offset]).fetchall()
    return {"total": total, "items": [_hydrate(conn, r) for r in rows]}


def delete_memory(conn: sqlite3.Connection, memory_id: str) -> list[str]:
    """Delete a memory and return stored file names of its attachments (caller unlinks them)."""
    if conn.execute("SELECT 1 FROM memories WHERE id=?", (memory_id,)).fetchone() is None:
        raise NotFound(memory_id)
    files = [r["stored_name"] for r in conn.execute(
        "SELECT stored_name FROM attachments WHERE memory_id=?", (memory_id,))]
    # A confirmed transcript is a copy of the memory's text, so it must go with it.
    conn.execute("DELETE FROM transcripts WHERE memory_id=?", (memory_id,))
    conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
    conn.commit()
    return files


def add_attachment(conn: sqlite3.Connection, memory_id: str | None, stored, attachment_id: str | None = None) -> dict[str, Any]:
    aid = attachment_id or uuid.uuid4().hex
    conn.execute(
        "INSERT INTO attachments(id,memory_id,kind,stored_name,original_name,mime,size,sha256,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (aid, memory_id, stored.kind, stored.stored_name, stored.original_name, stored.mime,
         stored.size, stored.sha256, now_iso()))
    if memory_id:
        conn.execute("UPDATE memories SET updated_at=? WHERE id=?", (now_iso(), memory_id))
    conn.commit()
    return dict(conn.execute("SELECT id,kind,original_name,mime,size,created_at FROM attachments WHERE id=?", (aid,)).fetchone())


def get_attachment(conn: sqlite3.Connection, attachment_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM attachments WHERE id=?", (attachment_id,)).fetchone()
    if row is None:
        raise NotFound(attachment_id)
    return row


def delete_attachment(conn: sqlite3.Connection, attachment_id: str) -> tuple[str, str | None]:
    row = get_attachment(conn, attachment_id)
    conn.execute("DELETE FROM attachments WHERE id=?", (attachment_id,))
    conn.commit()
    return row["stored_name"], row["memory_id"]


def facets(conn: sqlite3.Connection) -> dict[str, list[Any]]:
    return {
        "people": [{"name": r[0], "count": r[1]} for r in conn.execute(
            "SELECT name, COUNT(*) c FROM memory_people GROUP BY name ORDER BY c DESC, name")],
        "categories": [{"name": r[0], "count": r[1]} for r in conn.execute(
            "SELECT category, COUNT(*) c FROM memories GROUP BY category ORDER BY c DESC, category")],
        "tags": [{"name": r[0], "count": r[1]} for r in conn.execute(
            "SELECT tag, COUNT(*) c FROM memory_tags GROUP BY tag ORDER BY c DESC, tag")],
    }
