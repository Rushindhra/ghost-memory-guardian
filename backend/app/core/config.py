"""Application configuration.

All settings can be overridden with ``GHOST_*`` environment variables or a
``.env`` file.  Nothing in here points at a hosted service: the only network
endpoint is the local Ollama daemon, and non-loopback addresses are rejected
unless the user explicitly opts in.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
BOOTSTRAP_FILE = Path(os.environ.get("GHOST_CONFIG_FILE", REPO_ROOT / "ghost.config.json"))

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _bootstrap_data_dir() -> Path | None:
    """Read the storage directory chosen in the Privacy Center (applied at start-up)."""
    try:
        raw = json.loads(BOOTSTRAP_FILE.read_text(encoding="utf-8"))
        value = raw.get("data_dir")
        return Path(value) if value else None
    except (OSError, ValueError):
        return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GHOST_", env_file=".env", extra="ignore")

    # --- storage -----------------------------------------------------------
    data_dir: Path = Field(default_factory=lambda: _bootstrap_data_dir() or REPO_ROOT / "data")
    models_dir: Path = REPO_ROOT / "models"
    max_upload_mb: int = 200
    max_image_mb: int = 25

    # --- local LLM (Ollama) ------------------------------------------------
    ollama_url: str = "http://127.0.0.1:11434"
    allow_remote_llm: bool = False  # refuse non-loopback Ollama hosts unless true
    llm_model: str = "qwen3:4b"
    llm_timeout_s: float = 240.0
    llm_temperature: float = 0.2

    # --- embeddings --------------------------------------------------------
    embed_backend: Literal["auto", "sentence-transformers", "lexical"] = "auto"
    embed_model_path: Path | None = None  # default: models/embeddings/multilingual-e5-small
    # Calibrated by ``scripts/evaluate.py --calibrate``; per-backend defaults live in retrieval_service.
    min_score: float | None = None
    strong_score: float | None = None

    # --- transcription -----------------------------------------------------
    whisper_model_path: Path | None = None  # default: models/whisper/base
    whisper_language: str = ""  # empty = auto-detect
    whisper_compute_type: str = "int8"

    # --- web ---------------------------------------------------------------
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    session_hours: int = 12

    @field_validator("ollama_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    # ---- derived paths ----------------------------------------------------
    @property
    def db_path(self) -> Path:
        return self.data_dir / "ghost.sqlite3"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"

    @property
    def embed_dir(self) -> Path:
        return self.embed_model_path or self.models_dir / "embeddings" / "multilingual-e5-small"

    @property
    def whisper_dir(self) -> Path:
        return self.whisper_model_path or self.models_dir / "whisper" / "base"

    def ollama_is_loopback(self) -> bool:
        host = urlparse(self.ollama_url).hostname or ""
        return host in LOOPBACK_HOSTS

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.files_dir, self.index_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
