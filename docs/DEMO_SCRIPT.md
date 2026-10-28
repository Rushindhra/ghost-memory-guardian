# 3-minute demo script

*Prep (once, before recording):* `ollama serve` running with `qwen3:4b`, models downloaded, backend + UI started, **Settings → Load demo archive**. Warm the model by asking one question first (CPU first-token latency is the slowest part).

| Time | Do | Say |
|---|---|---|
| 0:00 | Overview. Point at the "Local-only · no telemetry" box and the live counts (14 memories, flagged *synthetic*). | "This is the Hartwell family — entirely fictional. Real archives look the same, and none of it leaves this laptop." |
| 0:20 | **Ask your memories** → click *Who taught Lily to knead bread dough?* | "I'm asking in plain language. The answer cites memory [1]; click the chip and it jumps to the exact excerpt." |
| 0:50 | Click *What is the capital of Australia?* | "Not in the archive, so GHOST refuses — 'I couldn't find that in your saved memories.' The model isn't even called. It never guesses." |
| 1:10 | **Oral History Studio** → record 10 s or upload a short clip → Transcribe. Edit one word. | "Whisper runs locally. Speech recognition makes mistakes, so the transcript is an editable draft; only after I confirm does it become a searchable memory." |
| 1:50 | **Timeline** → filter person *Elias*, tick three records → *Write family history*. | "A summary built *only* from the records I selected, with citations." |
| 2:10 | **Ghost Mode** → pick two memories, *Mysterious* → Write the story. Show *Verified facts* vs *Invented by the AI*. Then re-run with **Remembrance**. | "Clearly fiction, and it shows what's real versus invented. It never touches the archive — and there's a warm, no-horror remembrance mode." |
| 2:35 | **Privacy Center** → loopback endpoint, backup button, lock. Disconnect Wi-Fi and ask one more question. | "Only network address: Ollama on this machine. Export everything as JSON, Markdown or a ZIP. Pull the plug on the internet — it still works." |
| 2:55 | Close on Settings → component health. | "Open models, open formats, your data. That's GHOST." |

Only claim the offline step if you have actually completed `docs/OFFLINE.md`.
