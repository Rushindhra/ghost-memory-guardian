"""Shared FastAPI dependencies: context, DB connection, passphrase-lock enforcement."""
from __future__ import annotations

from typing import Iterator

import sqlite3
from fastapi import Depends, HTTPException, Request

from ..core.context import AppContext
from ..database import db

SESSION_COOKIE = "ghost_session"


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def get_conn(ctx: AppContext = Depends(get_ctx)) -> Iterator[sqlite3.Connection]:
    conn = ctx.conn()
    try:
        yield conn
    finally:
        conn.close()


def lock_enabled(conn: sqlite3.Connection) -> bool:
    return db.get_setting(conn, "lock_hash") is not None


def require_unlocked(request: Request, ctx: AppContext = Depends(get_ctx),
                     conn: sqlite3.Connection = Depends(get_conn)) -> None:
    if lock_enabled(conn) and not ctx.sessions.valid(request.cookies.get(SESSION_COOKIE)):
        raise HTTPException(status_code=401, detail="locked")
