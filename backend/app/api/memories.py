"""Memory Vault: CRUD, attachments, facets, related memories, timeline, file serving."""
from __future__ import annotations

import sqlite3
import subprocess
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from ..core.context import AppContext
from ..schemas.schemas import MemoryIn
from ..services import memory_service as ms
from ..services.file_store import UploadError
from .deps import get_conn, get_ctx, require_unlocked

router = APIRouter(prefix="/api", dependencies=[Depends(require_unlocked)])


def _404(exc: Exception) -> HTTPException:
    return HTTPException(404, "Not found.")


def compact(m: dict[str, Any], excerpt_chars: int = 220) -> dict[str, Any]:
    body = " ".join(m["body"].split())
    return {"id": m["id"], "title": m["title"], "memory_date": m["memory_date"], "category": m["category"],
            "people": m["people"], "tags": m["tags"], "is_demo": m["is_demo"], "source": m["source"],
            "excerpt": body[:excerpt_chars] + ("…" if len(body) > excerpt_chars else ""),
            "attachment_kinds": sorted({a["kind"] for a in m["attachments"]})}


@router.get("/memories")
def list_memories(q: str | None = Query(None, max_length=200), person: str | None = None, category: str | None = None,
                  tag: str | None = None, date_from: str | None = Query(None, pattern=r"^\d{4}(-\d{2}(-\d{2})?)?$"),
                  date_to: str | None = Query(None, pattern=r"^\d{4}(-\d{2}(-\d{2})?)?$"),
                  order: str = Query("recent", pattern="^(recent|oldest|newest)$"),
                  limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                  conn: sqlite3.Connection = Depends(get_conn)):
    res = ms.list_memories(conn, q, person, category, tag, date_from, date_to, limit, offset, order)
    return {"total": res["total"], "items": res["items"]}


@router.post("/memories", status_code=201)
def create_memory(body: MemoryIn, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    mem = ms.create_memory(conn, body)
    ctx.retriever.index_memory(conn, mem["id"])
    return mem


@router.get("/memories/facets")
def facets(conn: sqlite3.Connection = Depends(get_conn)):
    return ms.facets(conn)


@router.get("/memories/{memory_id}")
def get_memory(memory_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    try:
        return ms.get_memory(conn, memory_id)
    except ms.NotFound as exc:
        raise _404(exc)


@router.put("/memories/{memory_id}")
def update_memory(memory_id: str, body: MemoryIn, conn: sqlite3.Connection = Depends(get_conn),
                  ctx: AppContext = Depends(get_ctx)):
    try:
        mem = ms.update_memory(conn, memory_id, body)
    except ms.NotFound as exc:
        raise _404(exc)
    ctx.retriever.index_memory(conn, memory_id)
    return mem


@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: str, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    """Delete the record, its search index entries and every attached file from application storage."""
    try:
        ctx.retriever.remove_memory(conn, memory_id)
        stored = ms.delete_memory(conn, memory_id)
    except ms.NotFound as exc:
        raise _404(exc)
    removed = sum(ctx.files.delete(name) for name in stored)
    return {"deleted": memory_id, "files_removed": removed,
            "note": "Removed from GHOST's storage. Copies in backups, exports or SSD wear-levelling areas are not erased."}


@router.post("/memories/{memory_id}/attachments", status_code=201)
def add_attachment(memory_id: str, file: UploadFile = File(...), conn: sqlite3.Connection = Depends(get_conn),
                   ctx: AppContext = Depends(get_ctx)):
    try:
        ms.get_memory(conn, memory_id)
    except ms.NotFound as exc:
        raise _404(exc)
    try:
        stored = ctx.files.save(file.file, file.filename, {"photo", "audio", "document"})
    except UploadError as exc:
        raise HTTPException(400, str(exc))
    att = ms.add_attachment(conn, memory_id, stored)
    if stored.kind == "document" and stored.mime == "text/plain":  # index plain-text documents immediately
        text = ctx.files.path_for(stored.stored_name).read_text(encoding="utf-8", errors="replace")[:100_000]
        conn.execute("UPDATE attachments SET ocr_text=? WHERE id=?", (text, att["id"]))
        conn.commit()
    ctx.retriever.index_memory(conn, memory_id)
    return att | {"url": f"/api/files/{att['id']}"}


@router.delete("/attachments/{attachment_id}")
def delete_attachment(attachment_id: str, conn: sqlite3.Connection = Depends(get_conn),
                      ctx: AppContext = Depends(get_ctx)):
    try:
        stored_name, memory_id = ms.delete_attachment(conn, attachment_id)
    except ms.NotFound as exc:
        raise _404(exc)
    ctx.files.delete(stored_name)
    if memory_id:
        ctx.retriever.index_memory(conn, memory_id)
    return {"deleted": attachment_id}


@router.get("/files/{attachment_id}")
def serve_file(attachment_id: str, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    try:
        row = ms.get_attachment(conn, attachment_id)
        path = ctx.files.path_for(row["stored_name"])
    except (ms.NotFound, UploadError) as exc:
        raise _404(exc)
    if not path.exists():
        raise HTTPException(404, "The stored file is missing from disk.")
    headers = {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"}
    return FileResponse(path, media_type=row["mime"], headers=headers)


@router.post("/attachments/{attachment_id}/ocr")
def run_ocr(attachment_id: str, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    """Optional local OCR with the Tesseract binary (fixed argument list, no shell)."""
    import shutil
    try:
        row = ms.get_attachment(conn, attachment_id)
        path = ctx.files.path_for(row["stored_name"])
    except (ms.NotFound, UploadError) as exc:
        raise _404(exc)
    if row["kind"] != "photo":
        raise HTTPException(400, "OCR works on photographs and scans only.")
    exe = shutil.which("tesseract")
    if not exe:
        raise HTTPException(503, "Tesseract is not installed. Install it (see docs/INSTALL.md) to read scanned letters.")
    try:
        proc = subprocess.run([exe, str(path), "stdout"], capture_output=True, text=True, timeout=120, check=False)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "OCR took too long on this image.")
    text = proc.stdout.strip()
    if proc.returncode != 0:
        raise HTTPException(500, "Tesseract could not read this image.")
    conn.execute("UPDATE attachments SET ocr_text=? WHERE id=?", (text, attachment_id))
    conn.commit()
    if row["memory_id"]:
        ctx.retriever.index_memory(conn, row["memory_id"])
    return {"attachment_id": attachment_id, "characters": len(text), "text": text,
            "note": "OCR can misread handwriting and faded print; review before relying on it."}


@router.get("/memories/{memory_id}/related")
def related(memory_id: str, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    try:
        mem = ms.get_memory(conn, memory_id)
    except ms.NotFound as exc:
        raise _404(exc)
    found: dict[str, dict[str, Any]] = {}
    for hit in ctx.retriever.search(conn, f"{mem['title']}. {mem['body'][:300]}", k=8):
        if hit.memory_id != memory_id and ctx.retriever.confidence(hit) != "none":
            found[hit.memory_id] = {"reason": "similar content", "score": round(hit.score, 3)}
    for person in mem["people"]:
        for r in conn.execute("SELECT memory_id FROM memory_people WHERE name=? AND memory_id!=?", (person, memory_id)):
            entry = found.setdefault(r["memory_id"], {"reason": "", "score": 0.0})
            entry["reason"] = (entry["reason"] + "; " if entry["reason"] else "") + f"shares {person}"
    items = []
    for mid, info in list(found.items())[:8]:
        items.append(compact(ms.get_memory(conn, mid)) | info)
    items.sort(key=lambda i: (-("shares" in i["reason"]), -i["score"]))
    return {"items": items[:6]}


@router.get("/timeline")
def timeline(person: str | None = None, category: str | None = None, tag: str | None = None,
             date_from: str | None = Query(None, pattern=r"^\d{4}(-\d{2}(-\d{2})?)?$"),
             date_to: str | None = Query(None, pattern=r"^\d{4}(-\d{2}(-\d{2})?)?$"),
             q: str | None = Query(None, max_length=200), conn: sqlite3.Connection = Depends(get_conn)):
    res = ms.list_memories(conn, q, person, category, tag, date_from, date_to, limit=1000, order="oldest")
    years: dict[str, list[dict[str, Any]]] = {}
    undated: list[dict[str, Any]] = []
    for m in res["items"]:
        (years.setdefault(m["sort_date"][:4], []) if m["sort_date"] else undated).append(compact(m))
    return {"total": res["total"], "years": [{"year": y, "items": v} for y, v in sorted(years.items())],
            "undated": undated}
