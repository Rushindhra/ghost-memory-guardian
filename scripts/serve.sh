#!/usr/bin/env bash
# Single-process "production-style" run: backend serves the built UI at http://127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")/../backend"
exec ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
