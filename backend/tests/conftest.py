"""Test fixtures. AI services are replaced by clearly named fakes (FakeLLM/FakeTranscriber); the
retrieval stack, SQLite, FAISS, file store and API are real."""
from __future__ import annotations

import io
import struct
import wave
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.context import build_context
from app.main import create_app
from app.services.llm_service import LLMUnavailable
from app.services.transcription_service import TranscriptResult, TranscriptionUnavailable


class FakeLLM:
    """Scriptable stand-in for Ollama. NOT an AI: used only to test the surrounding logic."""
    model = "fake-llm"

    def __init__(self) -> None:
        self.reply: str | Exception = "Rosa baked cinnamon bread [1]."
        self.calls: list[list[dict[str, str]]] = []

    def status(self) -> dict[str, Any]:
        return {"engine": "fake", "reachable": True, "model_installed": True, "model": self.model,
                "installed_models": [self.model], "message": "", "url": "fake"}

    def chat(self, messages, json_mode: bool = False, temperature=None) -> str:
        self.calls.append(messages)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class FakeTranscriber:
    def __init__(self) -> None:
        self.available = True

    def status(self) -> dict[str, Any]:
        return {"engine": "fake", "ready": self.available, "package_installed": True, "model_present": self.available,
                "model_path": "fake", "message": "" if self.available else "not installed"}

    def transcribe(self, audio_path: Path, language: str = "") -> TranscriptResult:
        if not self.available:
            raise TranscriptionUnavailable("not installed")
        return TranscriptResult("Hello from the fake transcriber.", language or "en", 1.0, "fake-whisper")


def make_wav(seconds: float = 0.2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", 0) for _ in range(int(8000 * seconds))))
    return buf.getvalue()


PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", models_dir=tmp_path / "models", embed_backend="lexical",
                    max_upload_mb=1, max_image_mb=1)


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def stt() -> FakeTranscriber:
    return FakeTranscriber()


@pytest.fixture
def ctx(settings, llm, stt):
    return build_context(settings, llm=llm, transcriber=stt)


@pytest.fixture
def client(settings, ctx):
    app = create_app(settings, ctx)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def demo(client):
    assert client.post("/api/demo/load").status_code == 200
    return client


def mem(title="A memory", body="Some text about the lake house.", **kw):
    return {"title": title, "body": body, "memory_date": kw.get("memory_date", "1990-05-01"),
            "category": kw.get("category", "family"), "people": kw.get("people", ["Ann"]),
            "tags": kw.get("tags", ["lake"])}
