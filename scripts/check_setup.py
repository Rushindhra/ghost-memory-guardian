#!/usr/bin/env python
"""Verify prerequisites WITHOUT downloading anything. Exit code 0 = core app can run."""
from __future__ import annotations

import importlib.util
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
rows: list[tuple[str, str, str]] = []


def add(name: str, ok: bool | None, detail: str) -> None:
    rows.append(("OK  " if ok else "WARN" if ok is None else "FAIL", name, detail))


add("Python >= 3.11", sys.version_info >= (3, 11), sys.version.split()[0])
for mod, required in [("fastapi", True), ("uvicorn", True), ("faiss", True), ("numpy", True),
                      ("sentence_transformers", False), ("faster_whisper", False)]:
    found = importlib.util.find_spec(mod) is not None
    add(f"python package: {mod}", True if found else (False if required else None),
        "installed" if found else ("MISSING - pip install -r backend/requirements.txt" if required
                                    else "not installed (optional AI extra: backend/requirements-ml.txt)"))
node = shutil.which("node")
add("Node.js (frontend build)", True if node else None, node or "not found - only needed to build/develop the UI")
_built = (ROOT / "frontend" / "dist" / "index.html").exists()
add("frontend/dist built", True if _built else None, "present" if _built else "absent - run: cd frontend && npm ci && npm run build")
add("Tesseract OCR (optional)", True if shutil.which("tesseract") else None, shutil.which("tesseract") or "not found - photo OCR disabled")
add("ffmpeg (optional)", True if shutil.which("ffmpeg") else None, shutil.which("ffmpeg") or "not found - some audio formats may not decode")
add("embedding model", True if (ROOT / "models/embeddings/multilingual-e5-small/config.json").exists() else None,
    "present" if (ROOT / "models/embeddings/multilingual-e5-small/config.json").exists() else "absent - keyword fallback in use")
add("whisper model", True if (ROOT / "models/whisper/base/model.bin").exists() else None,
    "present" if (ROOT / "models/whisper/base/model.bin").exists() else "absent - transcription disabled")
try:
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:  # local only
        add("Ollama (local LLM)", True, f"reachable (HTTP {r.status})")
except Exception:
    add("Ollama (local LLM)", None, "not reachable - AI answers/Ghost Mode disabled until `ollama serve` + `ollama pull qwen3:4b`")
for status, name, detail in rows:
    print(f"[{status}] {name:<28} {detail}")
print("\nOK = ready, WARN = optional piece missing (feature degrades gracefully), FAIL = must fix.")
sys.exit(1 if any(s == "FAIL" for s, _, _ in rows) else 0)
