"""Embedding backends.

* ``SentenceTransformerEmbedder`` - the real neural model (default:
  multilingual-e5-small), loaded once, only from a local directory
  (``local_files_only``), never downloaded implicitly.
* ``LexicalEmbedder`` - a clearly labelled, dependency-free hashing vectoriser
  used when the neural model is not installed.  It is plain keyword-style
  matching, not AI, and the UI says so.

Model loading happens lazily behind a lock and is shared by all requests.
"""
from __future__ import annotations

import logging
import re
import threading
import unicodedata
from pathlib import Path
from typing import Protocol

import numpy as np

log = logging.getLogger("ghost.embeddings")

STOPWORDS = frozenset("""
a about above after again all also am an and any are as at be because been before being below between both but by
can could did do does doing down during each few for from further had has have having he her here hers him his how i
if in into is it its me more most my no nor not of off on once only or other our out over own same she should so some
such than that the their them then there these they this those through to too under until up very was we were what
when where which while who whom why will with would you your tell please remember story memory memories
""".split())

_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Lower-case, strip accents, drop stopwords, apply a very light stemmer."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    out: list[str] = []
    for tok in _WORD.findall(text):
        if tok in STOPWORDS or len(tok) < 2:
            continue
        for suffix in ("ing", "edly", "ed", "es", "ly", "s"):
            if len(tok) > len(suffix) + 3 and tok.endswith(suffix):
                tok = tok[: -len(suffix)]
                break
        out.append(tok)
    return out


class Embedder(Protocol):
    id: str
    dim: int
    neural: bool

    def embed_passages(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...


class LexicalEmbedder:
    """Signed feature hashing over word stems plus character trigrams (L2-normalised)."""

    id = "lexical-hash-v1"
    dim = 2048
    neural = False

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for tok in tokenize(text):
            for feature, weight in [(tok, 1.0)] + [(tok[i:i + 3], 0.25) for i in range(max(0, len(tok) - 2))]:
                h = _stable_hash(feature)
                vec[h % self.dim] += weight if (h >> 20) & 1 else -weight
        vec = np.sign(vec) * np.log1p(np.abs(vec))  # sub-linear damping of repeated terms
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._vector(t) for t in texts]).astype(np.float32) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._vector(text)


def _stable_hash(s: str) -> int:
    """FNV-1a 32-bit (Python's built-in hash() is salted per process)."""
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


class SentenceTransformerEmbedder:
    neural = True

    def __init__(self, model_dir: Path) -> None:
        from sentence_transformers import SentenceTransformer  # imported lazily: heavy

        self._model = SentenceTransformer(str(model_dir), device="cpu", local_files_only=True)
        self.dim = int(self._model.get_sentence_embedding_dimension())
        self.id = f"st:{model_dir.name}"
        # E5 models were trained with explicit prefixes; others ignore them.
        self._e5 = "e5" in model_dir.name.lower()
        self._lock = threading.Lock()

    def _encode(self, texts: list[str]) -> np.ndarray:
        with self._lock:
            return np.asarray(
                self._model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False),
                dtype=np.float32,
            )

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), np.float32)
        return self._encode([f"passage: {t}" if self._e5 else t for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode([f"query: {text}" if self._e5 else text])[0]


def neural_model_present(model_dir: Path) -> bool:
    return model_dir.is_dir() and (model_dir / "config.json").exists()


def build_embedder(backend: str, model_dir: Path) -> tuple[Embedder, str | None]:
    """Create the best available embedder.  Returns (embedder, note_for_ui)."""
    if backend == "lexical":
        return LexicalEmbedder(), "Lexical fallback selected by configuration."
    if backend in ("auto", "sentence-transformers"):
        if not neural_model_present(model_dir):
            return LexicalEmbedder(), (
                f"Neural embedding model not found at {model_dir}. Run scripts/download_models.py "
                "(or setup.ps1 -DownloadModels). Using the keyword-based lexical fallback."
            )
        try:
            return SentenceTransformerEmbedder(model_dir), None
        except Exception as exc:  # missing package, corrupt weights, ...
            log.warning("Neural embedder failed to load (%s): %s", type(exc).__name__, exc)
            return LexicalEmbedder(), f"Neural embedder could not be loaded ({type(exc).__name__}); using lexical fallback."
    return LexicalEmbedder(), None
