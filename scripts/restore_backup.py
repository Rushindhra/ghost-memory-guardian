#!/usr/bin/env python
"""Restore a GHOST backup (.zip from Privacy Center > Full backup) into an EMPTY data folder.

    python scripts/restore_backup.py ghost-backup.zip --data-dir ./data

Paths inside the zip are validated; the restore refuses to overwrite an existing database.
After restoring, start GHOST and press Settings > "Rebuild search index".
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.export_service import RestoreError, restore_backup  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip", type=Path)
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    a = ap.parse_args()
    try:
        result = restore_backup(a.zip, a.data_dir)
    except RestoreError as exc:
        print(f"Restore failed: {exc}")
        return 1
    print(f"Restored {result['restored_entries']} entries into {a.data_dir}. Rebuild the search index in Settings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
