"""Privacy Center: lock, storage location, exports/backup, honest privacy report."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..core import config as cfg
from ..core.context import AppContext
from ..core.security import MIN_PASSPHRASE_LEN, hash_passphrase, verify_passphrase
from ..database import db
from ..schemas.schemas import PassphraseIn, StorageIn
from ..services import export_service
from .deps import SESSION_COOKIE, get_conn, get_ctx, lock_enabled, require_unlocked

public = APIRouter(prefix="/api/privacy")
router = APIRouter(prefix="/api", dependencies=[Depends(require_unlocked)])


def _set_cookie(resp: Response, token: str, ctx: AppContext) -> None:
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="strict", max_age=ctx.settings.session_hours * 3600,
                    path="/")


@public.get("/lock-status")
def lock_status(request: Request, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    enabled = lock_enabled(conn)
    return {"enabled": enabled, "unlocked": (not enabled) or ctx.sessions.valid(request.cookies.get(SESSION_COOKIE))}


@public.post("/unlock")
def unlock(body: PassphraseIn, response: Response, conn: sqlite3.Connection = Depends(get_conn),
           ctx: AppContext = Depends(get_ctx)):
    stored = db.get_setting(conn, "lock_hash")
    if stored is None:
        return {"unlocked": True}
    wait = ctx.sessions.retry_after()
    if wait:
        raise HTTPException(429, f"Too many attempts. Try again in {wait} seconds.")
    if not verify_passphrase(body.passphrase, stored):
        ctx.sessions.record_failure()
        raise HTTPException(401, "Incorrect passphrase.")
    _set_cookie(response, ctx.sessions.create(), ctx)
    return {"unlocked": True}


@public.post("/logout")
def logout(request: Request, response: Response, ctx: AppContext = Depends(get_ctx)):
    ctx.sessions.revoke(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"unlocked": False}


@router.post("/privacy/lock/enable")
def enable_lock(body: PassphraseIn, response: Response, conn: sqlite3.Connection = Depends(get_conn),
                ctx: AppContext = Depends(get_ctx)):
    if lock_enabled(conn):
        raise HTTPException(409, "A passphrase is already set. Disable it first to change it.")
    if len(body.passphrase) < MIN_PASSPHRASE_LEN:
        raise HTTPException(422, f"Use at least {MIN_PASSPHRASE_LEN} characters.")
    db.set_setting(conn, "lock_hash", hash_passphrase(body.passphrase))
    _set_cookie(response, ctx.sessions.create(), ctx)
    return {"enabled": True, "note": ("The passphrase locks the app interface and API. It does NOT encrypt files on "
                                      "disk - use full-disk encryption (BitLocker, LUKS, FileVault) for that.")}


@router.post("/privacy/lock/disable")
def disable_lock(body: PassphraseIn, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    stored = db.get_setting(conn, "lock_hash")
    if stored is None:
        return {"enabled": False}
    if not verify_passphrase(body.passphrase, stored):
        ctx.sessions.record_failure()
        raise HTTPException(401, "Incorrect passphrase.")
    db.set_setting(conn, "lock_hash", None)
    ctx.sessions.revoke_all()
    return {"enabled": False}


@router.get("/privacy/report")
def report(conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    s = ctx.settings
    dir_size = lambda p: sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0  # noqa: E731
    return {
        "local_only": True,
        "telemetry": "none - GHOST contains no analytics, advertising or tracking code",
        "network_endpoints": [{"purpose": "Local language model (Ollama)", "url": s.ollama_url,
                               "loopback": s.ollama_is_loopback(), "remote_allowed": s.allow_remote_llm}],
        "storage": {"data_dir": str(s.data_dir), "database": str(s.db_path), "files": str(s.files_dir),
                    "index": str(s.index_dir), "models": str(s.models_dir),
                    "bytes": {"database": s.db_path.stat().st_size if s.db_path.exists() else 0,
                              "files": ctx.files.total_bytes(), "index": dir_size(s.index_dir)}},
        "lock_enabled": lock_enabled(conn),
        "encryption_at_rest": False,
        "logging": "Request bodies, memory text, transcripts and passphrases are never written to logs.",
        "deletion_notice": ("Deleting a record removes it, its search index entries and its attached files from "
                            "GHOST's storage. It does not erase copies in backups or exports you made, and on SSDs "
                            "or journaling file systems traces may remain until overwritten."),
        "encryption_recommendation": ("GHOST does not encrypt data on disk. Turn on full-disk encryption "
                                      "(BitLocker on Windows 11, LUKS on Linux, FileVault on macOS) and encrypt "
                                      "backup .zip files before storing them elsewhere."),
        "offline_note": ("Core features run offline once models are downloaded. 'Offline-ready' reports that the "
                         "needed local assets exist; it is not a substitute for the network-off test in docs/OFFLINE.md."),
    }


@router.post("/privacy/storage")
def set_storage(body: StorageIn):
    """Choose a different data folder. Applied on the next backend start; data is not moved automatically."""
    path = Path(body.data_dir).expanduser()
    if not path.is_absolute():
        raise HTTPException(422, "Enter an absolute folder path.")
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".ghost-write-test"
        probe.write_text("ok")
        probe.unlink()
    except OSError:
        raise HTTPException(400, "That folder cannot be created or written to.")
    cfg.BOOTSTRAP_FILE.write_text(json.dumps({"data_dir": str(path)}), encoding="utf-8")
    return {"data_dir": str(path), "restart_required": True,
            "note": "Restart the backend to use this folder. To keep your memories, download a backup first and "
                    "restore it into the new folder with scripts/restore_backup.py."}


# ------------------------------------------------------------------ exports
@router.get("/export/json")
def export_json(conn: sqlite3.Connection = Depends(get_conn)):
    return Response(json.dumps(export_service.export_json(conn), ensure_ascii=False, indent=2),
                    media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="ghost-export.json"'})


@router.get("/export/markdown")
def export_markdown(conn: sqlite3.Connection = Depends(get_conn)):
    return Response(export_service.export_markdown(conn), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="ghost-archive.md"'})


@router.get("/export/backup")
def backup(ctx: AppContext = Depends(get_ctx)):
    data = export_service.create_backup(ctx.settings.db_path, ctx.settings.files_dir)
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="ghost-backup.zip"'})
