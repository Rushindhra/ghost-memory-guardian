# Installation

Requirements: Python 3.11+ (tested on 3.13), Node.js 20+ (tested on 22) for the UI. Optional: Ollama, Tesseract (`tesseract-ocr`), ffmpeg. **No GPU is required.**

## Windows 11 (PowerShell)

```powershell
winget install Python.Python.3.13 OpenJS.NodeJS.LTS            # if missing
git clone <repo-url> ghost-memory-guardian ; cd ghost-memory-guardian
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1        # core (no model downloads)
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -WithML  # core + sentence-transformers + faster-whisper
```

Run (development, hot reload): `powershell -File scripts\dev.ps1` → <http://localhost:5173>.
Run (single process): `cd backend ; ..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000` → <http://127.0.0.1:8000>.

Separate commands:

```powershell
cd backend  ; ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000   # backend
cd frontend ; npm run dev                                                                 # frontend
cd backend  ; ..\.venv\Scripts\python.exe -m pytest                                       # backend tests
cd frontend ; npm test                                                                    # frontend tests
```

## Linux / macOS

```bash
scripts/setup.sh            # add --ml for the optional AI extras
scripts/dev.sh              # or scripts/serve.sh after the UI is built
```

## Local LLM with Ollama

```powershell
winget install Ollama.Ollama        # or https://ollama.com/download
ollama pull qwen3:4b                # ~2.5 GB; runs on CPU
```

Use another model by name in **Settings → Language model** (anything in `ollama list`) or `GHOST_LLM_MODEL` in `.env`. GHOST talks only to `127.0.0.1:11434` and refuses any other address unless you set `GHOST_ALLOW_REMOTE_LLM=true`.

| Model | RAM (approx.) | CPU speed (typical) | Use when |
|---|---|---|---|
| `qwen3:1.7b` | ~2 GB | quickest | 8 GB laptops; shorter, simpler answers |
| `qwen3:4b` (default) | ~3–4 GB | tens of seconds per answer on a modern CPU | best default quality/size |
| 7–8B models | 6–8 GB+ | a minute or more on CPU | 16 GB+ RAM, or a GPU |

These are rules of thumb, not measurements from this repository; your hardware decides. Ghost Mode and summaries generate more text and take longest.

## Embeddings and speech (one-time downloads)

```powershell
.\.venv\Scripts\python.exe scripts\download_models.py --all     # asks for confirmation; ~600 MB
```

Stored under `models/` (git-ignored) and loaded with `local_files_only`, so afterwards GHOST never needs the network for them. Pre-download on another machine and copy the `models/` folder if this one is offline. On Linux, the default PyTorch wheel includes CUDA libraries (several GB); for a smaller CPU-only install use `pip install torch --index-url https://download.pytorch.org/whl/cpu` before `requirements-ml.txt`.

## Verify

`python scripts/check_setup.py` lists what is ready and what is optional. In the app, **Settings → Component health** shows the same live.

## Lightweight mode (no LLM, no downloads)

Just run the app. Vault, keyword search, timeline, exports, Life Documents and the demo archive work; AI answers, summaries and Ghost Mode show setup guidance instead of guessing. Force keyword search with `GHOST_EMBED_BACKEND=lexical`.
