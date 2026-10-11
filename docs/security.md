# Privacy and security boundary

The private app assumes a trusted, single-user computer account. It is not designed for public hosting, untrusted local users or remote tunnel exposure.

- The launcher binds `127.0.0.1:8765` and restricts the `private/` folder to the owner on Windows (POSIX mode 0700 elsewhere).
- A random one-time fragment token bootstraps an eight-hour in-memory session. The fragment is removed before requests; it is not printed in logs. The token cannot be reused. The session cookie is HttpOnly and SameSite Strict; state-changing API calls need both a trusted Origin and a session-bound CSRF token. HTTP is intentionally loopback-only; the cookie is not claimed secure for public network transport.
- Trusted-host checks limit DNS-rebinding exposure. No permissive CORS is installed. CSP disallows foreign scripts, frames and network connections. User data is escaped before HTML insertion; external links accept only HTTP(S) and use noopener.
- Uploads accept bounded text PDF/DOCX documents, randomize saved filenames and reject oversized expanded DOCX files. Original names never become filesystem paths. No server endpoint serves `private/`, `.env` or sessions.
- Profile evidence is distinct from vacancy content. Verified claims quote a selected CV exactly and associated verified skills must occur in the quote. Self-reported claims require user approval. Imported suggestions are inferred and unapproved.
- Restore accepts bounded SQLite files with integrity/reference/schema checks and no views/triggers. Restored CV filesystem paths are cleared. Binary CVs are not included in database backups. Backups contain sensitive records; the user stores and deletes them separately.
- `.env`, CVs, databases, sessions, caches and local environments are excluded from Git and release ZIPs. The public builder reads no private path and emits only allowlisted assets from an explicit fictional seed. Public demo input should remain fictional.
- Telegram client credentials authorize only reading enabled accessible sources. JobFlow does not join private channels, bypass rate limits or send recruiter/application messages. A separately configured opt-in bot sends only to the owner's explicitly configured chat.
- Ollama traffic is loopback-only; no paid or remote AI endpoint is accepted. Bounded schema output selects existing evidence, with independent application validation and a factual fallback.

At-rest encryption is delegated to Windows account protections and, if enabled by the owner, BitLocker/device encryption. The app does not claim its SQLite/session files are independently encrypted. A compromised OS account can access them. Unusual PDFs can still stress parsing; process-isolated document parsing is a future hardening step.

Run `python -m scripts.security_scan` before publishing and inspect the staged file list. Dependency audit and tests are separate evidence, not substitutes for live security review. No credentials should ever be included in screenshots, logs or issue reports.
