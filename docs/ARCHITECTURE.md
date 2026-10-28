# Architecture

```
frontend/            React 19 + TypeScript + Vite + Tailwind 4 (9 screens, Vitest tests)
backend/app/
  main.py            app factory, security headers, narrow CORS + trusted hosts, serves built UI
  api/               thin routers: memories, ai, oral, documents, privacy, system (+ deps: conn, lock)
  core/              config (GHOST_* env), context (long-lived services), security (hashing, sessions)
  database/db.py     SQLite connect + versioned migrations (PRAGMA user_version)
  services/          memory, embedding, retrieval, llm, transcription, export, file_store, demo
  schemas/           strict Pydantic validation
backend/tests/       pytest (CRUD, retrieval, citation integrity, exports, file deletion, failures, concurrency)
demo/                synthetic archive + ground-truth questions
scripts/             setup, dev launchers, model download (opt-in), restore, evaluate, check_setup
```

## Request flow: "Ask your memories"

1. `POST /api/search` → `Retriever.search` embeds the query (E5 `query:` prefix) and searches FAISS; chunks are grouped per memory.
2. Each hit gets a confidence (`high/medium/low/none`) from calibrated score thresholds. **Only high/medium hits (max 4) become sources.** No sources → fixed refusal, the LLM is never called.
3. `OllamaClient.chat` receives numbered sources and a system prompt forbidding outside facts.
4. Post-checks in `api/ai.py`: citations pointing at non-existent sources are stripped; an answer with no valid citation is discarded and reported as not found; capitalised names/years absent from the sources are surfaced as warnings.
5. UI shows the answer with clickable `[n]` chips, supporting excerpts, scores, and which embedder was used.

If Ollama or the model is missing, the response is `ai_unavailable` with setup instructions — the matching memories are still shown. Nothing is ever fabricated.

## Design decisions

* **Models are loaded once** in `build_context` (start-up), never inside handlers; the Whisper model loads lazily on first use and is cached.
* **The index is derived data.** `Retriever.load` rebuilds from SQLite if the FAISS file/manifest is missing, corrupt, or from a different embedder; `POST /api/system/reindex` does it on demand. Source-of-truth vectors are float32 BLOBs in SQLite (no pickle anywhere); the FAISS file uses FAISS's native format and is only read from the app's own data folder.
* **Lexical fallback embedder** (signed feature hashing over word stems plus character trigrams, no model needed) keeps search working with zero downloads; the UI says which mode is active.
* **Uploads**: magic-byte sniffing (not the extension), size limits, generated IDs, no user-controlled paths. Files are served with `nosniff` and `Content-Security-Policy: sandbox`; the only subprocess is Tesseract, invoked with an argument list (no shell) on a server-generated path.
* **SQLite connections** are per-request; `check_same_thread=False` is required because FastAPI opens the dependency and runs the endpoint on different worker threads (regression-tested in `tests/test_concurrency.py`).
* **Privacy**: no request-body logging; uvicorn access lines with query strings are filtered; passphrase hashed with a salted slow KDF; failed attempts rate-limited; session cookie `HttpOnly`, `SameSite=Strict`.
* **Ghost Mode** never writes to the archive; the *Verified facts* panel is copied from the database, not produced by the model.
