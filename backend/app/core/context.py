"""Application context: long-lived services created once at start-up (never per request)."""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from ..database import db
from ..services.embedding_service import Embedder, build_embedder
from ..services.file_store import FileStore
from ..services.llm_service import LLM, OllamaClient
from ..services.retrieval_service import Retriever
from ..services.transcription_service import Transcriber, WhisperTranscriber
from .config import Settings
from .security import SessionStore

log = logging.getLogger("ghost")


@dataclass
class AppContext:
    settings: Settings
    files: FileStore
    sessions: SessionStore
    embedder: Embedder
    embed_note: str | None
    retriever: Retriever
    llm: LLM
    transcriber: Transcriber
    extras: dict[str, Any] = field(default_factory=dict)

    def conn(self) -> sqlite3.Connection:
        return db.connect(self.settings.db_path)


def build_context(settings: Settings, llm: LLM | None = None, transcriber: Transcriber | None = None,
                  embedder: Embedder | None = None) -> AppContext:
    """Create the context. ``llm``/``transcriber``/``embedder`` can be injected (used by tests)."""
    settings.ensure_dirs()
    conn = db.connect(settings.db_path)
    db.migrate(conn)
    note = None
    if embedder is None:
        embedder, note = build_embedder(settings.embed_backend, settings.embed_dir)
    model = db.get_setting(conn, "llm_model", settings.llm_model) or settings.llm_model
    language = db.get_setting(conn, "whisper_language", settings.whisper_language) or ""
    settings.whisper_language = language
    retriever = Retriever(embedder, settings.index_dir, settings.min_score, settings.strong_score)
    status = retriever.load(conn)
    conn.close()
    log.info("Vector index: %s (embedder=%s)", status, embedder.id)
    return AppContext(
        settings=settings,
        files=FileStore(settings.files_dir, settings.max_upload_mb * 1024 * 1024, settings.max_image_mb * 1024 * 1024),
        sessions=SessionStore(settings.session_hours * 3600),
        embedder=embedder, embed_note=note, retriever=retriever,
        llm=llm or OllamaClient(settings.ollama_url, model, settings.llm_timeout_s, settings.llm_temperature,
                                settings.allow_remote_llm, settings.ollama_is_loopback()),
        transcriber=transcriber or WhisperTranscriber(settings.whisper_dir, settings.whisper_compute_type),
    )
