"""Oral History Studio: upload -> (optional) local transcription -> edit -> confirm into a memory."""
from __future__ import annotations

import sqlite3
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..core.context import AppContext
from ..schemas.schemas import ConfirmIn, MemoryIn, TranscribeIn, TranscriptUpdate
from ..services import memory_service as ms
from ..services.file_store import StoredFile, UploadError
from ..services.transcription_service import TranscriptionUnavailable
from .deps import get_conn, get_ctx, require_unlocked

router = APIRouter(prefix="/api/oral", dependencies=[Depends(require_unlocked)])

DISCLAIMER = ("Speech recognition can make mistakes, especially with names, accents and background noise. "
              "Listen back and correct the transcript before saving it as a memory.")


def _row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    d["is_demo"] = bool(d["is_demo"])
    d["audio_url"] = f"/api/oral/{d['id']}/audio"
    d["disclaimer"] = DISCLAIMER
    d.pop("stored_name", None)
    return d


def _get(conn: sqlite3.Connection, tid: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM transcripts WHERE id=?", (tid,)).fetchone()
    if row is None:
        raise HTTPException(404, "Not found.")
    return row


@router.get("")
def list_transcripts(conn: sqlite3.Connection = Depends(get_conn)):
    rows = conn.execute("SELECT * FROM transcripts ORDER BY created_at DESC").fetchall()
    return {"items": [_row(r) for r in rows]}


@router.post("", status_code=201)
def upload(file: UploadFile = File(...), language: str = Form(""), transcribe: bool = Form(True),
           conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    try:
        stored: StoredFile = ctx.files.save(file.file, file.filename, {"audio"})
    except UploadError as exc:
        raise HTTPException(400, str(exc))
    tid, ts = uuid.uuid4().hex, ms.now_iso()
    conn.execute(
        "INSERT INTO transcripts(id,stored_name,original_name,mime,size,sha256,title,language,text,engine,status,"
        "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (tid, stored.stored_name, stored.original_name, stored.mime, stored.size, stored.sha256,
         stored.original_name.rsplit(".", 1)[0][:200], language, "", "none", "draft", ts, ts))
    conn.commit()
    message = None
    if transcribe:
        try:
            _run_transcription(ctx, conn, tid, language)
        except TranscriptionUnavailable as exc:
            message = str(exc)
    return {"transcript": _row(_get(conn, tid)), "message": message}


def _run_transcription(ctx: AppContext, conn: sqlite3.Connection, tid: str, language: str) -> float:
    row = _get(conn, tid)
    started = time.perf_counter()
    result = ctx.transcriber.transcribe(ctx.files.path_for(row["stored_name"]),
                                        language or ctx.settings.whisper_language)
    conn.execute("UPDATE transcripts SET text=?, language=?, engine=?, updated_at=? WHERE id=?",
                 (result.text, result.language, result.engine, ms.now_iso(), tid))
    conn.commit()
    return time.perf_counter() - started


@router.post("/{tid}/transcribe")
def transcribe(tid: str, body: TranscribeIn, conn: sqlite3.Connection = Depends(get_conn),
               ctx: AppContext = Depends(get_ctx)):
    row = _get(conn, tid)
    if row["status"] == "confirmed":
        raise HTTPException(409, "This transcript was already saved as a memory.")
    try:
        seconds = _run_transcription(ctx, conn, tid, body.language)
    except TranscriptionUnavailable as exc:
        raise HTTPException(503, str(exc))
    return {"transcript": _row(_get(conn, tid)), "seconds": round(seconds, 1)}


@router.put("/{tid}")
def edit(tid: str, body: TranscriptUpdate, conn: sqlite3.Connection = Depends(get_conn)):
    row = _get(conn, tid)
    if row["status"] == "confirmed":
        raise HTTPException(409, "Confirmed transcripts are stored in the memory; edit the memory instead.")
    engine = row["engine"] if row["engine"] not in ("none", "") else "manual"
    if body.text != row["text"] and engine != "manual" and not engine.endswith("+edited"):
        engine = engine + "+edited"
    conn.execute("UPDATE transcripts SET text=?, title=?, language=?, engine=?, updated_at=? WHERE id=?",
                 (body.text, body.title or row["title"], body.language or row["language"], engine, ms.now_iso(), tid))
    conn.commit()
    return _row(_get(conn, tid))


@router.post("/{tid}/confirm", status_code=201)
def confirm(tid: str, body: ConfirmIn, conn: sqlite3.Connection = Depends(get_conn),
            ctx: AppContext = Depends(get_ctx)):
    """Turn the reviewed transcript into a searchable memory that keeps the original recording."""
    row = _get(conn, tid)
    if row["status"] == "confirmed":
        raise HTTPException(409, "Already saved as a memory.")
    if not row["text"].strip():
        raise HTTPException(400, "The transcript is empty. Transcribe or type the text first.")
    mem = ms.create_memory(conn, MemoryIn(title=body.title, body=row["text"], memory_date=body.memory_date,
                                          category=body.category, people=body.people, tags=body.tags),
                           source="oral_history", is_demo=bool(row["is_demo"]))
    if row["stored_name"]:  # text-only demo transcripts have no recording
        stored = StoredFile(row["stored_name"], row["original_name"], row["mime"], "audio", row["size"], row["sha256"])
        ms.add_attachment(conn, mem["id"], stored)
    conn.execute("UPDATE transcripts SET status='confirmed', memory_id=?, updated_at=? WHERE id=?",
                 (mem["id"], ms.now_iso(), tid))
    conn.commit()
    ctx.retriever.index_memory(conn, mem["id"])
    return ms.get_memory(conn, mem["id"])


@router.get("/{tid}/audio")
def audio(tid: str, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    row = _get(conn, tid)
    try:
        path = ctx.files.path_for(row["stored_name"])
    except UploadError:
        raise HTTPException(404, "This transcript has no recording (it is text-only demo data).")
    if not path.exists():
        raise HTTPException(404, "The stored recording is missing from disk.")
    return FileResponse(path, media_type=row["mime"], headers={"X-Content-Type-Options": "nosniff"})


@router.delete("/{tid}")
def delete(tid: str, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    row = _get(conn, tid)
    conn.execute("DELETE FROM transcripts WHERE id=?", (tid,))
    conn.commit()
    if row["status"] != "confirmed" and row["stored_name"]:  # confirmed audio now belongs to the memory
        ctx.files.delete(row["stored_name"])
    return {"deleted": tid}
