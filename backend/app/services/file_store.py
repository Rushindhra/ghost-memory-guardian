"""Safe local file storage for uploads.

* Files are stored under generated UUID names; user-supplied names are never
  used for paths (only kept as display metadata after sanitising).
* Size limits are enforced while streaming.
* The content type is decided from magic bytes, not from the client header or
  extension, and only a fixed allow-list is accepted.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

CHUNK = 1024 * 1024


class UploadError(ValueError):
    """Raised for rejected uploads; message is safe to show to the user."""


@dataclass(frozen=True)
class StoredFile:
    stored_name: str
    original_name: str
    mime: str
    kind: str  # photo | audio | document
    size: int
    sha256: str


def sanitize_filename(name: str | None) -> str:
    base = (name or "upload").replace("\\", "/").split("/")[-1]
    base = re.sub(r"[^\w.\- ()]", "_", base, flags=re.UNICODE).strip(" .") or "upload"
    return base[:120]


def sniff(head: bytes) -> tuple[str, str, str] | None:
    """Return (mime, kind, extension) from leading bytes, or None if unsupported."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "photo", ".png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "photo", ".jpg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif", "photo", ".gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", "photo", ".webp"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav", "audio", ".wav"
    if head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return "audio/mpeg", "audio", ".mp3"
    if head.startswith(b"OggS"):
        return "audio/ogg", "audio", ".ogg"
    if head.startswith(b"fLaC"):
        return "audio/flac", "audio", ".flac"
    if head[4:8] == b"ftyp":
        return "audio/mp4", "audio", ".m4a"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "audio/webm", "audio", ".webm"
    if head.startswith(b"%PDF-"):
        return "application/pdf", "document", ".pdf"
    if b"\x00" not in head:
        try:
            head.decode("utf-8")
            return "text/plain", "document", ".txt"
        except UnicodeDecodeError:
            # a multi-byte character may be cut at the 4 KiB boundary
            try:
                head[:-3].decode("utf-8")
                return "text/plain", "document", ".txt"
            except UnicodeDecodeError:
                return None
    return None


class FileStore:
    def __init__(self, root: Path, max_bytes: int, max_image_bytes: int) -> None:
        self.root = root
        self.max_bytes = max_bytes
        self.max_image_bytes = max_image_bytes

    def save(self, stream: BinaryIO, original_name: str | None, allowed_kinds: set[str]) -> StoredFile:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / f".incoming-{uuid.uuid4().hex}"
        sha, size, head = hashlib.sha256(), 0, b""
        try:
            with tmp.open("wb") as out:
                while block := stream.read(CHUNK):
                    if not head:
                        head = block[:4096]
                    size += len(block)
                    if size > self.max_bytes:
                        raise UploadError(f"File is larger than the {self.max_bytes // (1024 * 1024)} MB limit.")
                    sha.update(block)
                    out.write(block)
            if size == 0:
                raise UploadError("The uploaded file is empty.")
            detected = sniff(head)
            if detected is None:
                raise UploadError("Unsupported file type. Use PNG/JPEG/GIF/WebP, WAV/MP3/M4A/OGG/FLAC/WebM, PDF or UTF-8 text.")
            mime, kind, ext = detected
            if kind not in allowed_kinds:
                raise UploadError(f"A {kind} file is not accepted here (expected: {', '.join(sorted(allowed_kinds))}).")
            if kind == "photo" and size > self.max_image_bytes:
                raise UploadError(f"Images are limited to {self.max_image_bytes // (1024 * 1024)} MB.")
            stored_name = f"{uuid.uuid4().hex}{ext}"
            tmp.replace(self.root / stored_name)
            return StoredFile(stored_name, sanitize_filename(original_name), mime, kind, size, sha.hexdigest())
        finally:
            tmp.unlink(missing_ok=True)

    def path_for(self, stored_name: str) -> Path:
        """Resolve a stored name, refusing anything that escapes the storage root."""
        if not re.fullmatch(r"[0-9a-f]{32}\.[a-z0-9]{2,5}", stored_name):
            raise UploadError("Invalid stored file name.")
        path = (self.root / stored_name).resolve()
        if self.root.resolve() not in path.parents:
            raise UploadError("Invalid stored file path.")
        return path

    def delete(self, stored_name: str) -> bool:
        try:
            path = self.path_for(stored_name)
        except UploadError:
            return False
        if path.exists():
            path.unlink()
            return True
        return False

    def total_bytes(self) -> int:
        if not self.root.exists():
            return 0
        return sum(p.stat().st_size for p in self.root.iterdir() if p.is_file())
