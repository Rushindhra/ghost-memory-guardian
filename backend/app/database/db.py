"""SQLite access and schema migrations (tracked with ``PRAGMA user_version``)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

# Append new migrations to the end; never edit an applied one.
MIGRATIONS: list[str] = [
    """
    CREATE TABLE memories (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        body TEXT NOT NULL DEFAULT '',
        memory_date TEXT,              -- YYYY, YYYY-MM or YYYY-MM-DD
        sort_date TEXT,                -- normalised YYYY-MM-DD for ordering
        category TEXT NOT NULL DEFAULT 'general',
        source TEXT NOT NULL DEFAULT 'manual',   -- manual | oral_history | demo
        is_demo INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX idx_memories_sort ON memories(sort_date);
    CREATE TABLE memory_people (
        memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        PRIMARY KEY (memory_id, name)
    );
    CREATE TABLE memory_tags (
        memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
        tag TEXT NOT NULL,
        PRIMARY KEY (memory_id, tag)
    );
    CREATE TABLE attachments (
        id TEXT PRIMARY KEY,
        memory_id TEXT REFERENCES memories(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,            -- photo | audio | document
        stored_name TEXT NOT NULL,
        original_name TEXT NOT NULL,
        mime TEXT NOT NULL,
        size INTEGER NOT NULL,
        sha256 TEXT NOT NULL,
        ocr_text TEXT,
        created_at TEXT NOT NULL
    );
    CREATE INDEX idx_attachments_memory ON attachments(memory_id);
    CREATE TABLE chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
        chunk_index INTEGER NOT NULL,
        text TEXT NOT NULL,
        embedding BLOB NOT NULL,
        embedder TEXT NOT NULL
    );
    CREATE INDEX idx_chunks_memory ON chunks(memory_id);
    CREATE TABLE transcripts (
        id TEXT PRIMARY KEY,
        stored_name TEXT NOT NULL,
        original_name TEXT NOT NULL,
        mime TEXT NOT NULL,
        size INTEGER NOT NULL,
        sha256 TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        language TEXT NOT NULL DEFAULT '',
        text TEXT NOT NULL DEFAULT '',
        engine TEXT NOT NULL DEFAULT '',     -- e.g. faster-whisper:base, or 'manual'
        status TEXT NOT NULL DEFAULT 'draft', -- draft | confirmed
        memory_id TEXT REFERENCES memories(id) ON DELETE SET NULL,
        is_demo INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE life_docs (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'note',   -- document|warranty|recipe|contact|date|task|note
        notes TEXT NOT NULL DEFAULT '',
        expiry_date TEXT,                    -- YYYY-MM-DD
        remind_date TEXT,                    -- YYYY-MM-DD
        is_demo INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
]


def connect(path: Path) -> sqlite3.Connection:
    # FastAPI runs the dependency that opens the connection and the endpoint that uses it on different worker
    # threads. Each connection belongs to exactly one request (never shared), so lifting SQLite's thread check is safe.
    conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    """Apply any pending migrations and return the resulting schema version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, script in enumerate(MIGRATIONS[current:], start=current + 1):
        conn.executescript(script)
        conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()
    return len(MIGRATIONS)


def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str | None) -> None:
    if value is None:
        conn.execute("DELETE FROM settings WHERE key = ?", (key,))
    else:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
    conn.commit()
