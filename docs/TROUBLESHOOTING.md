# Troubleshooting

| Symptom | Cause / fix |
|---|---|
| UI says **Backend unreachable** | Start the backend (`scripts\dev.ps1`). Check nothing else uses port 8000: `netstat -ano \| findstr :8000`; change with `--port` and set `GHOST_BACKEND=http://127.0.0.1:<port>` for `npm run dev`. |
| Port 5173 in use | The dev server uses `strictPort`; stop the other Vite process or edit `frontend/vite.config.ts`. |
| **AI setup needed** pill | Ollama is not running or the model is not installed: `ollama serve`, `ollama pull qwen3:4b`, then Settings → Re-check. |
| Answers take minutes / time out | CPU inference. Use a smaller model (`qwen3:1.7b`), close other apps, raise `GHOST_LLM_TIMEOUT_S`. |
| Out of memory / system freezes | Model too large for free RAM. Switch to a smaller model; quit browsers; avoid running Whisper and the LLM at once. |
| Search says **keyword fallback** | Embedding model not downloaded: `pip install -r backend/requirements-ml.txt`, `python scripts/download_models.py --embeddings`, restart, then Settings → Rebuild search index. |
| Transcription "setup needed" | `python scripts/download_models.py --whisper` and `pip install faster-whisper`. Install ffmpeg if a format will not decode. |
| `pip install` fails on faiss/numpy | Use Python 3.11–3.13 64-bit; upgrade pip; use the pinned `requirements.txt`. |
| `npm ci` fails | Use Node 20+; delete `frontend/node_modules` and retry. |
| Forgot the passphrase | There is no recovery by design. Restore a backup into a fresh data folder (`scripts/restore_backup.py`) or delete `ghost.sqlite3`'s `lock_hash` setting only if you accept editing the database yourself. |
| Search index looks stale or corrupt | Settings → Rebuild search index (it is rebuilt automatically at start-up if inconsistent). |
| Docker | `docker-compose.yml` is provided as a convenience and was **not** tested in this repository's environment. |
