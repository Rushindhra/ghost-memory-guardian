#!/usr/bin/env bash
# One command: backend on :8000 and Vite dev server on :5173 (open http://localhost:5173).
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT
(cd frontend && npm run dev)
