"""Life Documents: notes about warranties, recipes, contacts, dates; ICS reminder export."""
from __future__ import annotations

import sqlite3
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ..schemas.schemas import LifeDocIn
from ..services import export_service
from ..services.memory_service import now_iso
from .deps import get_conn, require_unlocked

router = APIRouter(prefix="/api/life-docs", dependencies=[Depends(require_unlocked)])

DISCLAIMER = ("Life Documents are personal notes for your own organisation. GHOST does not provide legal, medical "
              "or financial advice and does not replace professional guidance or the original documents.")


def _out(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["is_demo"] = bool(d["is_demo"])
    return d


def _fetch(conn: sqlite3.Connection, doc_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM life_docs WHERE id=?", (doc_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Not found.")
    return row


@router.get("")
def list_docs(q: str | None = Query(None, max_length=200), kind: str | None = None,
              conn: sqlite3.Connection = Depends(get_conn)):
    where, args = ["1=1"], []
    if q:
        where.append("(title LIKE ? OR notes LIKE ? OR kind LIKE ? OR expiry_date LIKE ? OR remind_date LIKE ?)")
        args += [f"%{q.strip()}%"] * 5
    if kind:
        where.append("kind=?")
        args.append(kind)
    rows = conn.execute(f"SELECT * FROM life_docs WHERE {' AND '.join(where)} "
                        "ORDER BY COALESCE(remind_date, expiry_date, '9999-12-31'), title", args).fetchall()
    return {"items": [_out(r) for r in rows], "disclaimer": DISCLAIMER}


@router.post("", status_code=201)
def create(body: LifeDocIn, conn: sqlite3.Connection = Depends(get_conn)):
    did, ts = uuid.uuid4().hex, now_iso()
    conn.execute("INSERT INTO life_docs(id,title,kind,notes,expiry_date,remind_date,created_at,updated_at) "
                 "VALUES(?,?,?,?,?,?,?,?)", (did, body.title, body.kind, body.notes, body.expiry_date,
                                             body.remind_date, ts, ts))
    conn.commit()
    return _out(_fetch(conn, did))


@router.put("/{doc_id}")
def update(doc_id: str, body: LifeDocIn, conn: sqlite3.Connection = Depends(get_conn)):
    _fetch(conn, doc_id)
    conn.execute("UPDATE life_docs SET title=?,kind=?,notes=?,expiry_date=?,remind_date=?,updated_at=? WHERE id=?",
                 (body.title, body.kind, body.notes, body.expiry_date, body.remind_date, now_iso(), doc_id))
    conn.commit()
    return _out(_fetch(conn, doc_id))


@router.delete("/{doc_id}")
def delete(doc_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    _fetch(conn, doc_id)
    conn.execute("DELETE FROM life_docs WHERE id=?", (doc_id,))
    conn.commit()
    return {"deleted": doc_id}


def _ics_response(rows: list[sqlite3.Row], name: str) -> Response:
    dated = [r for r in rows if r["remind_date"] or r["expiry_date"]]
    if not dated:
        raise HTTPException(400, "Nothing to export: add a reminder or expiry date first.")
    return Response(export_service.build_ics(dated), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/export.ics")
def export_all(conn: sqlite3.Connection = Depends(get_conn)):
    return _ics_response(conn.execute("SELECT * FROM life_docs").fetchall(), "ghost-reminders.ics")


@router.get("/{doc_id}/ics")
def export_one(doc_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return _ics_response([_fetch(conn, doc_id)], "ghost-reminder.ics")
