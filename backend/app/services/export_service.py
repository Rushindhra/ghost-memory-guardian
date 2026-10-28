"""JSON / Markdown / ICS exports and full backup + restore."""
from __future__ import annotations

import io
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from . import memory_service

BACKUP_FORMAT = 1


def export_json(conn: sqlite3.Connection) -> dict[str, Any]:
    memories = memory_service.list_memories(conn, limit=100000, order="oldest")["items"]
    for m in memories:
        for a in m["attachments"]:
            a.pop("url", None)
    docs = [dict(r) for r in conn.execute("SELECT * FROM life_docs ORDER BY title")]
    transcripts = [dict(r) for r in conn.execute(
        "SELECT id,original_name,title,language,text,engine,status,memory_id,created_at FROM transcripts")]
    return {
        "format": "ghost-export", "version": BACKUP_FORMAT,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "Plain JSON, readable without GHOST. Attachment files are in the backup .zip.",
        "memories": memories, "life_documents": docs, "transcripts": transcripts,
    }


def export_markdown(conn: sqlite3.Connection) -> str:
    out = ["# GHOST memory archive", "", f"_Exported {date.today().isoformat()}_", ""]
    for m in memory_service.list_memories(conn, limit=100000, order="oldest")["items"]:
        out += [f"## {m['title']}", ""]
        meta = [x for x in [f"**Date:** {m['memory_date']}" if m["memory_date"] else "",
                            f"**Category:** {m['category']}",
                            f"**People:** {', '.join(m['people'])}" if m["people"] else "",
                            f"**Tags:** {', '.join(m['tags'])}" if m["tags"] else "",
                            "**Source:** synthetic demo data" if m["is_demo"] else f"**Source:** {m['source']}"] if x]
        out += ["  \n".join(meta), "", m["body"].strip(), ""]
        if m["attachments"]:
            out += ["**Attachments:** " + ", ".join(a["original_name"] for a in m["attachments"]), ""]
    docs = conn.execute("SELECT * FROM life_docs ORDER BY title").fetchall()
    if docs:
        out += ["# Life documents", ""]
        for d in docs:
            out += [f"## {d['title']} ({d['kind']})", ""]
            if d["expiry_date"]:
                out.append(f"- Expires: {d['expiry_date']}")
            if d["remind_date"]:
                out.append(f"- Reminder: {d['remind_date']}")
            out += ["", d["notes"].strip(), ""]
    return "\n".join(out)


# ----------------------------------------------------------------- ICS ----
def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def _fold(line: str) -> str:
    raw, out = line.encode("utf-8"), []
    while len(raw) > 74:
        cut = 74
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:  # do not split a UTF-8 character
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = b" " + raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n".join(out)


def build_ics(docs: list[sqlite3.Row]) -> str:
    """RFC 5545 all-day events (with a 9am alarm) for reminder and expiry dates."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//GHOST//Life Documents//EN", "CALSCALE:GREGORIAN"]
    for d in docs:
        for label, key in (("Reminder", "remind_date"), ("Expires", "expiry_date")):
            if not d[key]:
                continue
            day = date.fromisoformat(d[key])
            nxt = date.fromordinal(day.toordinal() + 1)
            lines += [
                "BEGIN:VEVENT", f"UID:{d['id']}-{key}@ghost.local", f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{nxt:%Y%m%d}",
                f"SUMMARY:{_ics_escape(f'{label}: ' + d['title'])}",
                f"DESCRIPTION:{_ics_escape(d['notes'][:500])}",
                "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_ics_escape(d['title'])}", "TRIGGER:-P1D", "END:VALARM",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"


# --------------------------------------------------------- backup/restore --
def create_backup(db_path: Path, files_dir: Path) -> bytes:
    """Zip a consistent snapshot of the database plus every stored file."""
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "ghost.sqlite3"
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(snap))
        with dst:
            src.backup(dst)  # safe even while the app is running
        src.close()
        dst.close()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps({
                "format": "ghost-backup", "version": BACKUP_FORMAT,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}))
            zf.write(snap, "ghost.sqlite3")
            if files_dir.exists():
                for p in sorted(files_dir.iterdir()):
                    if p.is_file() and not p.name.startswith("."):
                        zf.write(p, f"files/{p.name}")
    return buf.getvalue()


class RestoreError(ValueError):
    pass


def restore_backup(zip_path: Path, data_dir: Path) -> dict[str, int]:
    """Restore a backup into ``data_dir`` (must not contain an existing database).

    Entries are validated by name, so a crafted zip cannot write outside ``data_dir``.
    """
    data_dir = data_dir.resolve()
    if (data_dir / "ghost.sqlite3").exists():
        raise RestoreError("The target folder already contains a GHOST database; restore into an empty folder.")
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise RestoreError("That file is not a valid backup archive.") from exc
    with zf:
        try:
            manifest = json.loads(zf.read("manifest.json"))
        except (KeyError, ValueError) as exc:
            raise RestoreError("Backup manifest is missing or unreadable.") from exc
        if manifest.get("format") != "ghost-backup" or manifest.get("version") != BACKUP_FORMAT:
            raise RestoreError("Unsupported backup format or version.")
        (data_dir / "files").mkdir(parents=True, exist_ok=True)
        restored = 0
        for info in zf.infolist():
            name = info.filename
            if name == "ghost.sqlite3":
                target = data_dir / "ghost.sqlite3"
            elif name.startswith("files/") and len(name.split("/")) == 2 and name.split("/")[1] \
                    and not name.endswith("/"):
                target = data_dir / "files" / name.split("/")[1]
            elif name == "manifest.json":
                continue
            else:
                raise RestoreError(f"Unexpected entry in backup: {name!r}")
            if data_dir not in target.resolve().parents:
                raise RestoreError(f"Unsafe path in backup: {name!r}")
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            restored += 1
    return {"restored_entries": restored}
