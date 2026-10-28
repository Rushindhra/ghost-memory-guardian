# Models and third-party licenses

GHOST is MIT-licensed. It downloads **no** weights by itself; you choose when (see `scripts/download_models.py`). Always confirm the license on the model card at download time — terms can change.

## Models

| Role | Default | License | Source of this information |
|---|---|---|---|
| Language model (via Ollama) | `qwen3:4b` (Qwen3-4B) | Apache-2.0 | Third-party model listing (promptlayer.com); **confirm on the Qwen model card/Ollama page before redistributing** |
| Embeddings | `intfloat/multilingual-e5-small` (~118M params, 100 languages) | MIT | Declared in the model's own README front matter on Hugging Face (checked) |
| Speech recognition | `Systran/faster-whisper-base` (CTranslate2 conversion of OpenAI Whisper base) | MIT | Third-party model listing (promptlayer.com); Whisper and faster-whisper are MIT upstream |

Any other Ollama model can be selected; its license is the user's responsibility. Outputs of these models can contain errors and reflect training-data bias.

## Software (runtime)

| Package | License (upstream) |
|---|---|
| FastAPI, Pydantic, pydantic-settings, python-multipart | MIT |
| Uvicorn, httpx, NumPy | BSD-3-Clause |
| faiss-cpu | MIT |
| sentence-transformers, transformers, huggingface_hub | Apache-2.0 |
| PyTorch | BSD-3-Clause |
| faster-whisper, CTranslate2 | MIT |
| Ollama | MIT |
| Tesseract OCR (optional) | Apache-2.0 |
| React, React DOM, React Router, Vite, Tailwind CSS, Vitest, Testing Library | MIT |
| Fraunces, Instrument Sans (bundled via `@fontsource`) | SIL Open Font License 1.1 |

License names above reflect each project's published license as generally known; they were not individually re-verified in this build (the sandbox has no access to most of those sites). Run `pip-licenses` / `npx license-checker` before distributing binaries.
