# Verification status (what is actually proven)

Last updated by the build run on Linux (Python 3.13.17, Node 22). Nothing here is aspirational.

## Verified by execution
| Item | Evidence |
|---|---|
| Backend test suite | `cd backend && ../.venv/bin/python -m pytest` → **46 passed** (CRUD, validation, file upload/deletion, path traversal, exports, backup + zip-slip restore, lock + throttling, retrieval, citation integrity, uncited/ungrounded handling, LLM-unavailable honesty, index rebuild after corruption, remote-LLM refusal, parallel requests). |
| Frontend | `npm test` → **10 passed**; `npm run build` (includes `tsc --noEmit`) succeeds. |
| Real-server browser pass | Chromium (Playwright) against a real uvicorn process: all 9 screens load with zero console errors and zero HTTP ≥400; Ask (answer + refusal), Timeline summary, Ghost Mode flows work; no horizontal overflow at 390 px width. This pass found and fixed a genuine bug (SQLite connection used across worker threads → HTTP 500) that the in-process tests could not see; a regression test was added. |
| Write-path UI pass | Through the real UI in Chromium: create → edit → delete a memory; create a Life Document and download a valid `.ics`; enable passphrase lock, download the backup ZIP, lock, reject a wrong passphrase, unlock, remove the lock; upload audio with no Whisper weights (recording kept, clear setup message, manual transcript still possible). |
| Retrieval evaluation (lexical fallback) | `scripts/evaluate.py --no-llm`: Recall@5 1.0, Precision@5 0.229 (ceiling ≈0.29), 13/14 answerable recognised, 5/5 unsupported rejected, ~7 ms average retrieval. See `EVAL_REPORT.md`. |
| Ollama HTTP integration | Exercised against a **mock Ollama server** (test harness only, extractive, not a language model) to prove the real client, grounding checks and UI end to end. |

## NOT verified here (build sandbox cannot download model weights or reach Hugging Face/Ollama)
* Neural retrieval quality with `multilingual-e5-small` (code path exists; falls back to keyword search if absent).
* Real answer/summary/story quality and latency with `qwen3:4b` on CPU (no latency numbers are claimed).
* faster-whisper transcription accuracy and speed (code path exists; the oral-history flow is tested with a fake transcriber and reports "setup needed" without weights).
* The **network-off** procedure in `OFFLINE.md` — therefore GHOST is *not* claimed to be verified offline.
* Windows 11 execution of `setup.ps1`/`dev.ps1` (written to mirror the tested Linux scripts), Docker files, Tesseract OCR on real scans, installing `requirements-ml.txt` (pip's resolver confirmed it is conflict-free; nothing was installed).

## Next steps for a maintainer
1. Install the models, run `evaluate.py` with Ollama up, commit the new `EVAL_REPORT.md`.
2. Run the offline procedure and record the result here.
3. Try a few real recordings (accented speech, noisy audio) and note Whisper-model-size trade-offs.
