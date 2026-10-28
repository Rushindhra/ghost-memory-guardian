#!/usr/bin/env python
"""Download the open-weight models GHOST uses - ONLY when you ask, and only after you confirm.

    python scripts/download_models.py --embeddings        # multilingual-e5-small (~470 MB, MIT)
    python scripts/download_models.py --whisper           # faster-whisper "base"  (~145 MB, MIT)
    python scripts/download_models.py --all --yes         # both, no prompt

The LLM is handled by Ollama:  ollama pull qwen3:4b  (~2.5 GB, Apache-2.0).
After the files exist under models/, GHOST loads them with local_files_only - no further network use.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    "embeddings": ("intfloat/multilingual-e5-small", ROOT / "models" / "embeddings" / "multilingual-e5-small", "~470 MB"),
    "whisper": ("Systran/faster-whisper-base", ROOT / "models" / "whisper" / "base", "~145 MB"),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embeddings", action="store_true")
    ap.add_argument("--whisper", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    a = ap.parse_args()
    wanted = [k for k in MODELS if a.all or getattr(a, k)]
    if not wanted:
        ap.print_help()
        return 2
    print("This will download from huggingface.co (the only time GHOST needs the internet for models):")
    for k in wanted:
        repo, dest, size = MODELS[k]
        print(f"  - {repo}  ({size})  ->  {dest}")
    try:
        answer = "y" if a.yes else input("Continue? [y/N] ")
    except EOFError:  # no terminal attached: treat as "no" rather than download silently
        answer = "n"
    if answer.strip().lower() != "y":
        print("Cancelled. Nothing was downloaded.")
        return 1
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("Install the helper first:  pip install -r backend/requirements-ml.txt")
        return 3
    for k in wanted:
        repo, dest, _ = MODELS[k]
        dest.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {repo} ...")
        snapshot_download(repo_id=repo, local_dir=str(dest))
        print(f"  done: {dest}")
    print("\nNext: restart the backend, then open Settings to confirm each component shows ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
