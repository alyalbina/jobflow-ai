# Technical and product decisions

## Scope

Single-user, local-first MVP for a trusted OS account. The owner controls enabled sources, factual evidence and final submissions. FastAPI plus a buildless interface avoids a second runtime/bundler for local use. SQLite provides atomic persistence without a database service. An asyncio loop supervises polling and notifications; work occurs only while the local app is running. Closing the laptop does not create a cloud scheduled task.

## Ingestion contract

The canonical message key is `(source_id, message_id)`. Each successful poll persists the message and advances its cursor in one transaction. New-message events insert with `advance=False`; only ordered catch-up changes the high-water mark. A bounded poll of 200 resumes above that mark, preserving backlog across restarts. Initial history uses the configured latest limit (default 50), then sorts it before committing. Polls do not request unrelated history.

Normalized exact content hashes deduplicate cross-source posts. A single-message edit updates its existing job and preserves its CRM identity. When multiple source messages share a job, editing one detaches it rather than rewriting all sources. Soft deletion marks a job unavailable only when no remaining source message is live. Manual structured overrides are not overwritten by reparsing.

Telegram can omit delete events or chat IDs; deletion by a bare message ID would be unsafe, so it is never done. Recent reconciliation checks 30 known message IDs per source. It does not promise complete historical deletion detection. Sources are checked through the authorized client; a public landing page is a separate weaker signal.

## Data model and provenance

Ten tables: settings, sources, jobs, messages, cvs, letters, applications, status_events, feedback and outbox. SQLite foreign keys are enabled on every connection; transactions roll back on failure. WAL supports reads during intake. CV versions are immutable records with optional parent IDs. Approved facts retain provenance; generated letters snapshot the exact facts used. A freely edited letter creates a new saved version and loses automatic factual certification; previously linked application versions remain unchanged.

The matching model is configurable but deliberately transparent. Its dimensions are design choices, not learned hiring probabilities. Candidate evidence, candidate preferences and vacancy requirements are distinct inputs. Salary comparisons require matching currencies and periods; authorization gaps are never silently treated as a known inability to work.

## AI boundary

Basic Mode constructs drafts from approved facts. Local AI receives a bounded vacancy excerpt and approved evidence only through a fixed localhost Ollama endpoint. A JSON schema restricts output to existing evidence IDs; the application independently validates types, membership, uniqueness and length. Model output never changes the candidate's biography. Invalid IDs, malformed output and network timeouts use the deterministic fallback.

Facts remain in their approved language. This avoids presenting an unreviewed translation as a verified quote. The user can approve truthful equivalents as self-reported statements. Broad extraction or semantic matching quality is not implied by a successful small local model probe.

## Application and delivery semantics

Preparation is not submission. Applied requires explicit manual confirmation and a recorded date. Status events preserve historical stage membership for cohort denominators. Editing notes does not fabricate a transition. CV and cover-letter IDs identify the application package used.

Bot delivery uses a durable unique outbox key and a frequency-limited digest. Intent is written before the network call. Telegram Bot API does not provide the same idempotency contract as a database transaction; a timeout may mean delivery happened. Such records become `delivery_unknown` and are not auto-retried. Interrupted `sending` records are also retained for inspection on restart. This deliberately avoids claiming exactly-once external delivery.

## Public/private split

The private server is bound to loopback and serves authenticated APIs. The public build contains only explicit web assets and a fresh synthetic dataset generated in a temporary database. It has a browser-only adapter and cannot access the owner's filesystem, local SQLite database, sessions or credentials. The build has no backend deployment and no hidden paid service. Demo metrics reflect fictional actions and outcomes.

## Performance and tradeoffs

Lists are paginated in the UI. The private initial response loads the latest 1,000 jobs plus vacancies linked to CRM records; `/api/jobs` searches the full archive in 50-row pages. Current scoring scans the local collection on request rather than maintaining a second stale score index. Large-archive benchmarks and precomputed score invalidation are separate work; their performance is not claimed without testing. Telegram polling remains bounded and rate-aware.
