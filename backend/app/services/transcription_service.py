"""Local speech-to-text with faster-whisper.

The Whisper model is loaded once, lazily, from a local directory with no
network access.  If the package or weights are missing, ``TranscriptionUnavailable``
explains how to fix it; the Oral History Studio then still works with manual transcripts.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger("ghost.transcription")


class TranscriptionUnavailable(RuntimeError):
    pass


@dataclass
class TranscriptResult:
    text: str
    language: str
    duration_s: float
    engine: str


class Transcriber(Protocol):
    def status(self) -> dict[str, Any]: ...
    def transcribe(self, audio_path: Path, language: str = "") -> TranscriptResult: ...


class WhisperTranscriber:
    def __init__(self, model_dir: Path, compute_type: str = "int8") -> None:
        self.model_dir, self.compute_type = model_dir, compute_type
        self._model: Any = None
        self._lock = threading.Lock()

    def _weights_present(self) -> bool:
        return self.model_dir.is_dir() and (self.model_dir / "model.bin").exists()

    def status(self) -> dict[str, Any]:
        try:
            import faster_whisper  # noqa: F401
            package = True
        except ImportError:
            package = False
        present = self._weights_present()
        msg = ""
        if not package:
            msg = "faster-whisper is not installed. Run: pip install faster-whisper"
        elif not present:
            msg = (f"Whisper model not found at {self.model_dir}. Download it once with "
                   "`python scripts/download_models.py --whisper` and keep it for offline use.")
        return {"engine": "faster-whisper", "package_installed": package, "model_present": present,
                "model_path": str(self.model_dir), "ready": package and present, "message": msg}

    def _load(self) -> Any:
        with self._lock:
            if self._model is None:
                st = self.status()
                if not st["ready"]:
                    raise TranscriptionUnavailable(st["message"])
                from faster_whisper import WhisperModel
                try:
                    self._model = WhisperModel(str(self.model_dir), device="cpu",
                                               compute_type=self.compute_type, local_files_only=True)
                except Exception as exc:
                    raise TranscriptionUnavailable(
                        f"The Whisper model at {self.model_dir} could not be loaded ({type(exc).__name__}). "
                        "Re-download it or choose another model path.") from exc
            return self._model

    def transcribe(self, audio_path: Path, language: str = "") -> TranscriptResult:
        model = self._load()
        try:
            segments, info = model.transcribe(str(audio_path), language=language or None, vad_filter=True,
                                              beam_size=5)
            text = " ".join(seg.text.strip() for seg in segments).strip()
        except Exception as exc:  # undecodable / corrupt audio
            log.warning("Transcription failed: %s", type(exc).__name__)
            raise TranscriptionUnavailable(
                "That audio file could not be decoded. Try WAV or MP3, or type the transcript manually.") from exc
        return TranscriptResult(text, info.language, float(info.duration), f"faster-whisper:{self.model_dir.name}")
