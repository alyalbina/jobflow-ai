# Executed verification — JobFlow AI

Date: 11 October 2026. Local environment: Windows, Python 3.12.2. All inputs used during these checks were fictional. No real CV, Telegram account session or recruiter communication was used.

## Automated checks

`python -m pytest -q`: **56 passed**, no skips, in 9.29 seconds on the last run before publication preparation. The current Starlette TestClient reports one upstream deprecation warning about its httpx adapter; assertions pass. CI results are recorded after remote execution below.

Coverage includes bilingual extraction/missing fields, non-vacancy classifications, required versus preferred skills, inferred-evidence exclusion, confirmed versus unknown eligibility, seniority/language rules, atomic message/cursor persistence, deduplication, edits/deletes, durable status history, manual Applied confirmation, CV evidence provenance through tailored versions, immutable edited letter versions, archive pagination, DOCX imports/exports, grounded drafts, unsupported/network-failed local model responses, mock Telethon backfill/catch-up/reconciliation/flood wait, notification deduplication/ambiguous delivery, API authentication/Origin/CSRF/Host checks, manual corrections, weekly measurement, backup/restore/delete and public-build canary isolation. Eight Node-based scenarios compare the public and private matching policy.

Runtime dependency audit: **29 exact pinned distributions, no known vulnerabilities reported** by `pip-audit` against PyPI advisories on this date. This is an advisory database check, not proof that every dependency is safe. Build tools and development dependencies are separate from the runtime lock.

Ruff checks/format, JavaScript syntax and the public credential/artifact boundary scan are part of local checks and CI. A public-build test places synthetic private CV/session canaries next to the builder and asserts they are absent from the published package.

## Browser and export checks

Checked the actual FastAPI app against a separate fictional QA database on loopback, and the static demo in the Codex browser:

- Navigation, score-sorted discovery and an empty search result.
- Detailed original text, missing-field notices and matching explanations.
- Applied without confirmation is rejected; Preparing is persisted and appears in Kanban.
- Basic Mode creates and saves a letter using approved fictional facts. Later edits create a new version, keeping earlier application references unchanged.
- An unsupported manual letter edit is saved with a factual-review warning.
- A bilingual fictional DOCX uploads through the UI; extracted quotes stay inferred until explicitly approved.
- An approved quote retains its CV reference; tailoring creates version 3 derived from version 2, preserving the original.
- Mobile layout and navigation at 390×844. Root content fits the viewport; Kanban/table content scrolls within its container.
- PDF export rendered through Poppler and visually inspected: Latin/Cyrillic text and bullets are readable with no clipping in the one-page fictional fixture. DOCX content is reopened in automated tests.

Actual captures: [desktop](screenshots/overview-desktop.jpg), [mobile](screenshots/overview-mobile.jpg), [mobile CV Studio](screenshots/studio-mobile.jpg), [dark theme](screenshots/settings-dark.jpg). Additional final publication captures are added after verification.

The installed project `.venv` imports the actual FastAPI and Telethon modules. A launcher smoke check verified loopback configuration, one-time authentication, 22 disabled sources and an empty owner profile/database. Its browser opening, server loop and native ACL command were substituted. The Codex Windows sandbox denies `WRITE_DAC`, so owner-operated folder permission tightening and the full double-click launch remain unverified here. The product retains its fail-fast permission check. No real private data was used.

Installer QA caught an empty legacy `pyaes` wheel produced by the older pip even though `pip check` passed. The installer now pins modern build tools, rebuilds that dependency without the cache and checks actual module imports; the repaired installed runtime passed imports. CI exercises the same build-tool bootstrap on Windows and Linux.

## Installed local AI observation

Ollama was already installed with qwen3:8b (5.2 GB on disk). Windows reported about 13.9 GB physical RAM. No model was downloaded. An unconstrained synthetic probe returned an invalid ID. A schema-constrained warm probe returned a supported SQL fact in 1.91 seconds. The **actual production `select_facts` function**, run cold on the same fictional SQL/UX choice, returned only `f-sql` in **20.95 seconds**, with no fallback warning. The model was unloaded after testing; the Ollama service was left running.

These observations demonstrate execution and a bounded evidence guard. They do not establish general matching accuracy, translation quality, latency guarantees or product impact. Basic Mode remains usable without Ollama.

## Telegram evidence and remaining owner activation

Twenty of the twenty-two configured source usernames had public Telegram pages in the web check. `opento_crypto` and `web30job` could not be confirmed by that web tool; they are unverified, not declared nonexistent. See [source report](sources.md). Sources start disabled, and actual account access is checked by the authorized client.

Initial history, catch-up, edits/deletes, flood wait and failure recovery were exercised with deterministic fake Telethon clients. **Live owner-authorized ingestion, Telegram login/2FA, real bot delivery and real candidate matching remain unverified**, because credentials and a real CV were not supplied. Activate with the local [Windows guide](windows-guide.md), then verify enabled sources and one personal notification. Never paste credentials or login codes into chat.

## Remote publication

Repository: [alyalbina/jobflow-ai](https://github.com/alyalbina/jobflow-ai). [Implementation PR #1](https://github.com/alyalbina/jobflow-ai/pull/1) merged on 11 October 2026 after all four checks passed. The checked feature commit was `38985a0d82f9ebf1282233bb3568d660c13530f3`; its [PR CI run](https://github.com/alyalbina/jobflow-ai/actions/runs/38162716937) completed successfully.

The merged commit `63598dcf263f3846582b9d637d0ac3db8ba35b48` passed [main CI](https://github.com/alyalbina/jobflow-ai/actions/runs/38162847380): Windows and Linux, each with Python 3.12 and 3.13. Each job executes actual runtime imports, Ruff, 56 tests, JavaScript syntax, the isolated public build/boundary scan and pinned runtime dependency audit. The [Pages workflow](https://github.com/alyalbina/jobflow-ai/actions/runs/38162847376) completed both build and deploy successfully.

Visited the actual deployed [HTTPS sandbox](https://alyalbina.github.io/jobflow-ai/) in a fresh browser tab. The initial state showed 24 fictional vacancies and six fictional application records. Country filtering returned six UAE vacancies. A detail view displayed original text, supported skills and unspecified fields. Applied without confirmation was rejected; Preparing was saved and appeared in Kanban. Basic Mode generated and saved a letter composed of approved fictional statements. The deployed [English case study](https://alyalbina.github.io/jobflow-ai/case-study.html) showed all twelve sections and the link to this report. No real Telegram or personal CV data was used.

Actual deployed captures: [workspace](screenshots/published-demo.jpg), [case study](screenshots/published-case.jpg). These are observations of the published product, not mockups. Documentation and these captures are committed after the checked implementation merge; final delivery also rechecks its CI/deployment.

## Practical limits

No formal user interviews, time savings, hiring conversion improvement, load-scale guarantee, complete offline edit/delete coverage or calibrated matching accuracy are claimed. Initial backfill affects discovery delay. Rule extraction and normalized-text deduplication have known edge cases. The private feed starts with 1,000 records and offers a server-side archive search; arbitrary large archives need further performance work. Tests are contract checks, not a labelled field-quality benchmark.
