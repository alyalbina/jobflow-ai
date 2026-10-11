# JobFlow AI execution plan

## Decisions

Local-first, single-user Python 3.12 application. FastAPI serves an accessible buildless HTML/CSS/JavaScript interface and a same-origin API; SQLite transactions preserve ingestion cursors and CRM history. Telethon reads only enabled channels accessible to the authorized account. A supervised asyncio loop schedules bounded ingestion and bot notifications. Basic Mode uses deterministic parsing, evidence-linked scoring and factual letter templates. Optional localhost Ollama selects existing evidence with an explicit fallback; it never invents candidate claims.

The public GitHub Pages demo uses an allowlisted synthetic dataset and a browser-only adapter. It has no private API routes, sessions, CVs, network credentials or access to the local application's database. Existing portfolio repositories are outside the scope.

## Phases

1. Discovery/design: architecture, metric contract, data model and privacy boundaries — implemented and reviewed.
2. Working MVP: ingestion/storage/parser/matching/discovery UI — implemented and locally checked.
3. CRM and CV Studio: immutable evidence/version references, letters, timeline/follow-ups — implemented and locally checked.
4. Optional local AI: availability/hardware check and bounded evidence selection — implemented and locally checked.
5. Analytics/notifications: event-based funnels and durable notification outbox — implemented and locally checked.
6. QA/publication: 56 passing local tests, desktop/mobile browser checks, isolated public demo, README/case/career materials completed. Implementation PR merged after Windows/Linux CI passed on Python 3.12/3.13. GitHub Pages published and its actual discovery, CRM, factual draft and twelve-section case checked in the browser; see [executed evidence](validation.md).

## Connection dependencies

Live Telegram ingestion needs the owner's api_id/api_hash and official account authorization. Secrets and login codes are entered locally by the owner, never in chat or Git. A separate BotFather token/chat ID is needed only for opt-in personal notifications. Real CVs are added privately by the owner. No real Telegram run, user research, time savings or hiring conversion improvement will be claimed without evidence.

## Acceptance scenarios

Bounded initial import; durable catch-up without cursor gaps; deduplication; edit/delete propagation; flood wait/reconnection; missing-field parsing; supported/unknown/missing skill distinctions; confirmed seniority/geography exclusions; manual vacancy corrections; manual applied confirmation; status timeline; private CV import/version history; grounded English/Russian letter drafts; follow-up notifications; backup/restore/delete; empty/error states; desktop/mobile filtering/CRM; public demo cannot call local endpoints; secrets/dependency checks; GitHub CI and public Pages verification.

## Verification checkpoint

56 local tests passed, including eight public/private scorer parity scenarios. Ruff/JavaScript/public-boundary checks and pinned dependency audit executed. Installed qwen3:8b executed the production evidence selector on fictional input. Browser QA covered discovery, CRM, CV upload/provenance/tailoring, letter edits and mobile navigation. The installed product environment passed module imports and the private login/empty-state contract. Windows native folder ACL tightening could not be verified from the Codex sandbox and remains an owner-operated launch check. Live Telegram and bot activation remain owner-local dependencies; no real operation or hiring improvement is claimed.
