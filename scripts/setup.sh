#!/usr/bin/env bash
# Linux/macOS setup. Installs pinned dependencies; never downloads model weights by itself.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r backend/requirements-dev.txt
if [ "${1:-}" = "--ml" ]; then .venv/bin/pip install -r backend/requirements-ml.txt; fi
(cd frontend && npm ci && npm run build)
.venv/bin/python scripts/check_setup.py || true
echo "Next: scripts/dev.sh   (add models later with: python scripts/download_models.py --all)"
