"""Chunking, persistent vector index and retrieval.

Source of truth for vectors is the ``chunks`` table (float32 BLOBs, no pickle).
The FAISS index file is only a cache: it is validated against the database at
start-up and rebuilt from the stored vectors (or by re-embedding) whenever it
is missing, stale or corrupted.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .embedding_service import Embedder, tokenize

log = logging.getLogger("ghost.retrieval")

CHUNK_CHARS, OVERLAP_CHARS = 700, 120

# Defaults are provisional; run ``python scripts/evaluate.py --calibrate`` on your archive.
DEFAULT_THRESHOLDS = {  # (min_score, strong_score)
    True: (0.80, 0.86),    # neural (e5 cosine scores are compressed into a high range)
    False: (0.22, 0.38),   # lexical hashing
}


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Paragraph-aware chunking with a small overlap for long paragraphs."""
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    buf = ""
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) + 2 <= size:
            buf = f"{buf}\n\n{para}" if buf else para
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        if len(para) <= size:
            buf = para
            continue
        start = 0
        while start < len(para):
            end = min(len(para), start + size)
            if end < len(para):  # prefer to break on sentence end / whitespace
                cut = max(para.rfind(". ", start, end), para.rfind(" ", start + size // 2, end))
                end = cut + 1 if cut > start + size // 3 else end
            chunks.append(para[start:end].strip())
            if end >= len(para):
                break
            start = max(end - overlap, start + 1)
    if buf:
        chunks.append(buf)
    return [c for c in chunks if c]


class _NumpyIndex:
    """Minimal exact inner-product index used when FAISS is not installed."""

    def __init__(self, dim: int) -> None:
        self.dim, self.ids, self.mat = dim, np.zeros(0, np.int64), np.zeros((0, dim), np.float32)

    @property
    def ntotal(self) -> int:
        return len(self.ids)

    def add_with_ids(self, vecs: np.ndarray, ids: np.ndarray) -> None:
        self.mat, self.ids = np.vstack([self.mat, vecs]), np.concatenate([self.ids, ids])

    def remove(self, ids: np.ndarray) -> None:
        keep = ~np.isin(self.ids, ids)
        self.mat, self.ids = self.mat[keep], self.ids[keep]

    def search(self, q: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        if not self.ntotal:
            return np.zeros((1, 0), np.float32), np.zeros((1, 0), np.int64)
        scores = self.mat @ q[0]
        order = np.argsort(-scores)[:k]
        return scores[order][None, :], self.ids[order][None, :]


@dataclass
class Hit:
    memory_id: str
    score: float
    chunk_ids: list[int]
    excerpts: list[str]
    overlap: int = 0  # query/chunk keyword overlap, used to sanity-check semantic scores


class Retriever:
    def __init__(self, embedder: Embedder, index_dir: Path, min_score: float | None = None,
                 strong_score: float | None = None) -> None:
        self.embedder = embedder
        self.index_dir = index_dir
        d_min, d_strong = DEFAULT_THRESHOLDS[embedder.neural]
        self.min_score = min_score if min_score is not None else d_min
        self.strong_score = strong_score if strong_score is not None else d_strong
        self._lock = threading.RLock()
        self._index: Any = None
        self.index_status = "not loaded"
        self.faiss_available = True
        try:
            import faiss  # noqa: F401
        except ImportError:
            self.faiss_available = False

    # ---- index plumbing ---------------------------------------------------
    def _new_index(self) -> Any:
        if self.faiss_available:
            import faiss
            return faiss.IndexIDMap2(faiss.IndexFlatIP(self.embedder.dim))
        return _NumpyIndex(self.embedder.dim)

    @property
    def _paths(self) -> tuple[Path, Path]:
        return self.index_dir / "chunks.faiss", self.index_dir / "chunks.meta.json"

    def _save(self) -> None:
        if not self.faiss_available or self._index is None:
            return
        import faiss
        self.index_dir.mkdir(parents=True, exist_ok=True)
        idx_path, meta_path = self._paths
        faiss.write_index(self._index, str(idx_path))
        meta_path.write_text(json.dumps({"embedder": self.embedder.id, "dim": self.embedder.dim,
                                         "count": int(self._index.ntotal)}), encoding="utf-8")

    def load(self, conn: sqlite3.Connection) -> str:
        """Load the persisted index if consistent with the DB, else rebuild. Returns a status string."""
        with self._lock:
            stale = conn.execute("SELECT COUNT(*) FROM chunks WHERE embedder != ?", (self.embedder.id,)).fetchone()[0]
            if stale:
                log.info("Re-embedding %d chunks for embedder %s", stale, self.embedder.id)
                return self.rebuild(conn, reembed=True)
            total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            idx_path, meta_path = self._paths
            if self.faiss_available and idx_path.exists():
                try:
                    import faiss
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    if meta.get("embedder") == self.embedder.id and meta.get("count") == total:
                        index = faiss.read_index(str(idx_path))
                        if index.ntotal == total and index.d == self.embedder.dim:
                            self._index, self.index_status = index, f"loaded from disk ({total} chunks)"
                            return self.index_status
                except Exception as exc:  # missing/corrupt file - fall through to rebuild
                    log.warning("Vector index unusable (%s); rebuilding from database.", type(exc).__name__)
            return self.rebuild(conn)

    def rebuild(self, conn: sqlite3.Connection, reembed: bool = False) -> str:
        """Rebuild the index from stored vectors; ``reembed`` recomputes vectors from the source text."""
        with self._lock:
            if reembed:
                conn.execute("DELETE FROM chunks")
                conn.commit()
                for row in conn.execute("SELECT id FROM memories").fetchall():
                    self._write_chunks(conn, row["id"])
            index = self._new_index()
            rows = conn.execute("SELECT id, embedding FROM chunks WHERE embedder=? ORDER BY id", (self.embedder.id,)).fetchall()
            if rows:
                vecs = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
                ids = np.array([r["id"] for r in rows], dtype=np.int64)
                index.add_with_ids(vecs, ids)
            self._index = index
            self._save()
            self.index_status = f"rebuilt from database ({len(rows)} chunks)"
            return self.index_status

    # ---- maintaining chunks -------------------------------------------------
    def _memory_text(self, conn: sqlite3.Connection, memory_id: str) -> tuple[str, str]:
        m = conn.execute("SELECT title, body, memory_date, category FROM memories WHERE id=?", (memory_id,)).fetchone()
        people = [r[0] for r in conn.execute("SELECT name FROM memory_people WHERE memory_id=?", (memory_id,))]
        ocr = [r[0] for r in conn.execute(
            "SELECT ocr_text FROM attachments WHERE memory_id=? AND ocr_text IS NOT NULL", (memory_id,))]
        body = m["body"] + ("\n\n" + "\n\n".join(ocr) if ocr else "")
        header = f"{m['title']}" + (f" ({m['memory_date']})" if m["memory_date"] else "")
        if people:
            header += f" - people: {', '.join(people)}"
        return header, body

    def _write_chunks(self, conn: sqlite3.Connection, memory_id: str) -> list[int]:
        header, body = self._memory_text(conn, memory_id)
        pieces = chunk_text(body) or [header]
        vecs = self.embedder.embed_passages([f"{header}\n{p}" for p in pieces])
        new_ids: list[int] = []
        for i, (piece, vec) in enumerate(zip(pieces, vecs)):
            cur = conn.execute(
                "INSERT INTO chunks(memory_id,chunk_index,text,embedding,embedder) VALUES(?,?,?,?,?)",
                (memory_id, i, piece, np.asarray(vec, np.float32).tobytes(), self.embedder.id))
            new_ids.append(cur.lastrowid)
        conn.commit()
        return new_ids

    def index_memory(self, conn: sqlite3.Connection, memory_id: str) -> int:
        """(Re)index one memory.  Safe to call after create/update."""
        with self._lock:
            self._remove_ids(self._chunk_ids(conn, memory_id))
            conn.execute("DELETE FROM chunks WHERE memory_id=?", (memory_id,))
            new_ids = self._write_chunks(conn, memory_id)
            if self._index is None:
                self.load(conn)
            else:
                rows = conn.execute(
                    f"SELECT id, embedding FROM chunks WHERE id IN ({','.join('?' * len(new_ids))})", new_ids).fetchall()
                self._index.add_with_ids(
                    np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows]),
                    np.array([r["id"] for r in rows], dtype=np.int64))
                self._save()
            return len(new_ids)

    def remove_memory(self, conn: sqlite3.Connection, memory_id: str) -> None:
        with self._lock:
            self._remove_ids(self._chunk_ids(conn, memory_id))
            conn.execute("DELETE FROM chunks WHERE memory_id=?", (memory_id,))
            conn.commit()
            self._save()

    @staticmethod
    def _chunk_ids(conn: sqlite3.Connection, memory_id: str) -> list[int]:
        return [r[0] for r in conn.execute("SELECT id FROM chunks WHERE memory_id=?", (memory_id,))]

    def _remove_ids(self, ids: list[int]) -> None:
        if not ids or self._index is None:
            return
        arr = np.array(ids, dtype=np.int64)
        if self.faiss_available:
            self._index.remove_ids(arr)
        else:
            self._index.remove(arr)

    # ---- searching ---------------------------------------------------------
    def search(self, conn: sqlite3.Connection, query: str, k: int = 5,
               allowed_memory_ids: set[str] | None = None) -> list[Hit]:
        """Return up to ``k`` memories ranked by their best-matching chunk."""
        with self._lock:
            if self._index is None:
                self.load(conn)
            if self._index.ntotal == 0:
                return []
            q = np.asarray(self.embedder.embed_query(query), np.float32)[None, :]
            scores, ids = self._index.search(q, min(self._index.ntotal, max(k * 6, 30)))
        per_memory: dict[str, Hit] = {}
        q_tokens = set(tokenize(query))
        for score, cid in zip(scores[0], ids[0]):
            if cid < 0:
                continue
            row = conn.execute("SELECT memory_id, text FROM chunks WHERE id=?", (int(cid),)).fetchone()
            if row is None or (allowed_memory_ids is not None and row["memory_id"] not in allowed_memory_ids):
                continue
            hit = per_memory.get(row["memory_id"])
            overlap = len(q_tokens & set(tokenize(row["text"])))
            adj = float(score)
            if hit is None:
                per_memory[row["memory_id"]] = Hit(row["memory_id"], adj, [int(cid)], [row["text"]], overlap)
            elif len(hit.excerpts) < 2:
                hit.chunk_ids.append(int(cid))
                hit.excerpts.append(row["text"])
                hit.overlap = max(hit.overlap, overlap)
        return sorted(per_memory.values(), key=lambda h: -h.score)[:k]

    def confidence(self, hit: Hit) -> str:
        """Human-readable band; ``overlap`` guards against high-but-meaningless semantic scores."""
        overlap = hit.overlap
        if hit.score >= self.strong_score and (overlap > 0 or not self.embedder.neural):
            return "high"
        if hit.score >= self.min_score and (overlap > 0 or hit.score >= self.strong_score):
            return "medium"
        if hit.score >= self.min_score:
            return "low"
        return "none"

    def is_supported(self, hits: list[Hit]) -> bool:
        """True when at least one hit is a credible match (used to reject unsupported questions)."""
        return any(self.confidence(h) in ("high", "medium") for h in hits)

    def stats(self, conn: sqlite3.Connection) -> dict[str, Any]:
        return {
            "embedder": self.embedder.id,
            "neural": self.embedder.neural,
            "dim": self.embedder.dim,
            "faiss": self.faiss_available,
            "chunks": conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
            "index_status": self.index_status,
            "min_score": self.min_score,
            "strong_score": self.strong_score,
        }
