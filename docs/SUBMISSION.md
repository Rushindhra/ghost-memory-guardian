# Challenge submission — GHOST (Ghost in the Machine)

## One-line pitch
GHOST helps families keep their stories — in their own words and voices — in a private archive that an open-weight AI can search, summarise and retell, entirely on their own computer.

## The problem
Oral histories, letters and recipes vanish when the person who holds them does. The tools that could help (cloud assistants, "digital legacy" startups) require handing the most private material a family owns to a company's servers and a company's future. Elders, diaspora communities and grieving families have the strongest need and the strongest reasons for caution.

## What GHOST does
* **Preserve:** vault with photos, audio, documents and OCR; local speech-to-text turns recordings into editable, confirmed, searchable text (multilingual).
* **Recall:** ask in natural language; get answers that cite the actual memories, with excerpts and relevance — or an honest "I couldn't find that in your saved memories."
* **Understand:** timeline, related memories, and family-history summaries built only from records the user selects.
* **Reimagine, respectfully:** Ghost Mode writes *labelled fiction* from chosen memories, separating verified facts from invented details; Remembrance mode removes horror entirely. GHOST never claims to reach or reproduce the dead.
* **Stay in control:** passphrase lock, JSON/Markdown/ZIP export, documented restore, local-only operation, no telemetry.
* **Practical life archive:** warranties, recipes, emergency contacts and dates with calendar-ready `.ics` reminders.

## Why open innovation matters here
* **Privacy:** open weights run where the data lives. No prompt, memory or voice recording is transmitted anywhere; the one network endpoint is Ollama on loopback and GHOST refuses non-local ones by default.
* **Model choice:** the LLM, embedder and speech model are each swappable with a setting or path. A family can pick a 1.7B model for an old laptop or a larger one for a workstation, or a language-specific model for their heritage language.
* **Reproducibility:** pinned dependencies, deterministic ground-truth evaluation (`scripts/evaluate.py`), a synthetic dataset, and a report that states what was and was not measured.
* **Local control:** SQLite and plain files; every feature except AI generation works with nothing installed but Python.
* **Long-term preservation:** an archive that depends on a commercial API stops working when the API changes. GHOST's data is readable without GHOST, and its AI parts can be re-created from open models indefinitely.
* **Trustworthy AI by construction:** grounding is enforced in code, not left to prompts — invalid citations are removed, uncited answers discarded, unsupported questions refused before the model is called, and unfamiliar names/years flagged.

## Honest status
See [`STATUS.md`](STATUS.md): what has been run and measured, and what still needs verifying on a machine with the model weights (neural retrieval quality, real-LLM answer quality, Whisper accuracy, the network-off test).

## Responsible-use notes
Fiction is labelled; deletion semantics and backups are explained; encryption-at-rest is *not* provided and is called out with recommendations; Life Documents carry a not-professional-advice notice.
