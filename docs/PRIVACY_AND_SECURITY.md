# Privacy and security model

**Promises (implemented and tested where noted)**
* No hosted AI APIs; no analytics, ads or telemetry code. The sole network address is local Ollama; non-loopback is refused by default (tested).
* Logs never contain memory text, transcripts, passphrases or request bodies; uvicorn access lines carrying query strings are suppressed.
* Passphrase lock: scrypt-hashed with a per-install salt, constant-time compare, back-off after failures, `HttpOnly` + `SameSite=Strict` session cookie. Every API route except lock-status/unlock/logout/health requires an unlocked session.
* Uploads are type-sniffed, size-limited and stored under generated names; paths are never taken from the client.
* CORS is limited to the local dev origins; `TrustedHostMiddleware` allows only localhost; `X-Content-Type-Options`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` on all responses.
* Errors return a generic message; internals are never echoed to the browser.

**Not promised**
* Data at rest is **not encrypted**. Use full-disk encryption: BitLocker (Windows 11 Pro/Home with device encryption), LUKS (Linux), FileVault (macOS). Encrypt backups.
* The lock does not stop someone with file-system access to your user account or an unlocked session.
* Binding is to `127.0.0.1`; do not expose the port to a network without adding TLS and stronger authentication.
* Local LLM output can be wrong. Treat citations and the "not found in sources" warnings as aids, not guarantees.

**Respectful by design:** GHOST never claims to contact the dead or reproduce a person. Ghost Mode is labelled fiction on-screen, lists what the model invented, never edits the archive, and offers a Remembrance mode with no horror elements. Life Documents are personal notes, not legal, medical or financial advice.
