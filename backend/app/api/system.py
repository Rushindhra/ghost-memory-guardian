"""Health, dashboard overview, settings, reindex and demo-data endpoints."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, Depends

from .. import __version__
from ..core.context import AppContext
from ..database import db
from ..schemas.schemas import RuntimeSettingsIn
from ..services import demo_service, memory_service as ms
from ..services.embedding_service import neural_model_present
from .deps import get_conn, get_ctx, require_unlocked
from .memories import compact

public = APIRouter(prefix="/api/system")
router = APIRouter(prefix="/api", dependencies=[Depends(require_unlocked)])


def build_health(ctx: AppContext, conn: sqlite3.Connection) -> dict:
    llm = ctx.llm.status()
    stt = ctx.transcriber.status()
    stats = ctx.retriever.stats(conn)
    llm_ready = bool(llm.get("reachable") and llm.get("model_installed"))
    stt_ready = bool(stt.get("ready"))
    neural = ctx.embedder.neural
    return {
        "backend": {"ok": True, "version": __version__},
        "database": {"ok": True, "schema_version": conn.execute("PRAGMA user_version").fetchone()[0],
                     "path": str(ctx.settings.db_path)},
        "embeddings": stats | {"model_present": neural_model_present(ctx.settings.embed_dir), "note": ctx.embed_note,
                               "ready": True,
                               "mode": "neural semantic search" if neural else "keyword (lexical) fallback"},
        "transcription": stt,
        "llm": llm | {"ready": llm_ready},
        "offline": {
            "core_archive_ready": True,
            "semantic_search_ready": neural,
            "transcription_ready": stt_ready,
            "llm_ready": llm_ready,
            "offline_ready": neural and stt_ready and llm_ready and ctx.settings.ollama_is_loopback(),
            "explanation": ("'Offline-ready' means every local model and dependency needed for the full feature set is "
                            "present on this computer. Whether your device is currently online is shown separately by "
                            "the browser. Verify with the network-off test in docs/OFFLINE.md."),
        },
        "telemetry": False,
    }


@public.get("/health")
def health(conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    """Unauthenticated, but exposes no memory content - only component status."""
    h = build_health(ctx, conn)
    h["llm"].pop("installed_models", None)
    return h


@router.get("/system/overview")
def overview(conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    audio_memories = conn.execute("SELECT COUNT(DISTINCT memory_id) FROM attachments WHERE kind='audio'").fetchone()[0]
    confirmed = conn.execute("SELECT COUNT(*) FROM transcripts WHERE status='confirmed'").fetchone()[0]
    recent = ms.list_memories(conn, limit=5, order="recent")["items"]
    preview = ms.list_memories(conn, limit=6, order="oldest", date_from="0001")["items"]
    horizon = (date.today() + timedelta(days=90)).isoformat()
    upcoming = [dict(r) for r in conn.execute(
        "SELECT id,title,kind,expiry_date,remind_date FROM life_docs WHERE "
        "(remind_date IS NOT NULL AND remind_date<=? AND remind_date>=?) OR (expiry_date IS NOT NULL AND expiry_date<=? AND expiry_date>=?) "
        "ORDER BY COALESCE(remind_date, expiry_date) LIMIT 5",
        (horizon, date.today().isoformat(), horizon, date.today().isoformat()))]
    s = ctx.settings
    health = build_health(ctx, conn)
    return {
        "total_memories": total,
        "audio_stories": max(audio_memories, confirmed),
        "demo_memories": conn.execute("SELECT COUNT(*) FROM memories WHERE is_demo=1").fetchone()[0],
        "life_documents": conn.execute("SELECT COUNT(*) FROM life_docs").fetchone()[0],
        "recent": [compact(m) for m in recent],
        "timeline_preview": [compact(m) for m in preview],
        "upcoming_reminders": upcoming,
        "storage": {"database_bytes": s.db_path.stat().st_size if s.db_path.exists() else 0,
                    "files_bytes": ctx.files.total_bytes(), "data_dir": str(s.data_dir)},
        "ai": {"llm_ready": health["llm"]["ready"], "llm_model": health["llm"].get("model"),
               "search_mode": health["embeddings"]["mode"], "transcription_ready": health["transcription"]["ready"]},
    }


@router.get("/system/settings")
def get_settings_view(conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    st = ctx.llm.status()
    return {"llm_model": getattr(ctx.llm, "model", ""), "installed_models": st.get("installed_models", []),
            "whisper_language": ctx.settings.whisper_language, "ollama_url": ctx.settings.ollama_url,
            "embed_model_path": str(ctx.settings.embed_dir), "whisper_model_path": str(ctx.settings.whisper_dir),
            "note": "Model folders and the Ollama address are set in .env (GHOST_* variables) and need a restart."}


@router.put("/system/settings")
def put_settings(body: RuntimeSettingsIn, conn: sqlite3.Connection = Depends(get_conn),
                 ctx: AppContext = Depends(get_ctx)):
    if body.llm_model is not None:
        ctx.llm.model = body.llm_model  # type: ignore[attr-defined]
        db.set_setting(conn, "llm_model", body.llm_model)
    if body.whisper_language is not None:
        ctx.settings.whisper_language = body.whisper_language
        db.set_setting(conn, "whisper_language", body.whisper_language)
    return get_settings_view(conn, ctx)


@router.post("/system/reindex")
def reindex(conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    """Rebuild every embedding and the vector index from the source records."""
    status = ctx.retriever.rebuild(conn, reembed=True)
    return {"status": status, **ctx.retriever.stats(conn)}


@router.get("/demo/status")
def demo_status(conn: sqlite3.Connection = Depends(get_conn)):
    n = conn.execute("SELECT COUNT(*) FROM memories WHERE is_demo=1").fetchone()[0]
    return {"loaded": n > 0, "memories": n,
            "label": "Synthetic demo archive: the fictional Hartwell family. Contains no real personal data."}


@router.post("/demo/load")
def demo_load(conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    return demo_service.load_demo(conn, ctx.retriever)


@router.delete("/demo")
def demo_remove(conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    return demo_service.remove_demo(conn, ctx.retriever, ctx.files)
