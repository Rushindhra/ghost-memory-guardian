# Offline operation

**Offline-ready** = every local model and dependency needed for the full feature set exists on this computer (Settings shows it). **Currently offline** = the device has no network (the sidebar shows the browser's status). GHOST works the same either way once models are downloaded.

## What touches the network

| Component | When |
|---|---|
| `scripts/download_models.py` | Only when you run it and confirm. |
| `ollama pull` | Only when you run it. |
| Backend ↔ Ollama | `127.0.0.1` loopback only. |
| Everything else | Never. No analytics, fonts are bundled (`@fontsource`), no CDN. |

## Network-off test procedure (do this before claiming offline-readiness)

1. Download models and run the app once; confirm Settings shows every component ready.
2. Disconnect Wi-Fi/Ethernet (or enable Airplane mode). Optionally also block outbound traffic with the OS firewall.
3. Restart Ollama and the backend. Confirm the sidebar says **offline**.
4. Walk through: load demo → Ask (semantic) → record/upload a clip and transcribe → Ghost Mode → Timeline summary → export a backup.
5. Record the result in `docs/STATUS.md`.

**This test has not been run for this repository** (the build environment blocks model downloads), so GHOST reports *offline-ready* only as a statement about installed components, and this project does not claim a verified offline run.
