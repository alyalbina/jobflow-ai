# JobFlow AI — international portfolio materials

Use these as project descriptions, after reviewing that each statement reflects your own understanding and contribution. Development used AI engineering assistance. Do not describe the mock-tested Telegram integration as a completed live account deployment until you authorize and verify it.

## English CV entry

**JobFlow AI — personal job discovery and application workspace**  
Independent product project · 2026  
[GitHub](https://github.com/alyalbina/jobflow-ai) · [Synthetic demo](https://alyalbina.github.io/jobflow-ai/)

- Defined a local-first job-search workflow and implemented Telegram ingestion, conservative vacancy extraction and explainable ranking across role, skills, experience, geography and seniority.
- Built an application CRM with confirmed submission states, event history and follow-ups, plus CV versions and English/Russian drafts grounded in approved evidence; optional local Ollama falls back to deterministic templates.
- Designed event-based application analytics and bounded relevance evaluation, separating an isolated fictional public demo from private credentials, CVs and SQLite records.

**Stack:** Python, FastAPI, SQLite, Telethon, asyncio, JavaScript, HTML/CSS, Ollama, pytest, Ruff, GitHub Actions, GitHub Pages, python-docx, ReportLab.

Avoid adding “saved X hours”, “improved response by Y%”, “production adoption” or “95% matching accuracy” without measured evidence. The demo's 75% response rate is fictional.

## LinkedIn Projects

**JobFlow AI | Explainable job discovery and application workflow**

I scoped and built a personal job-search workspace that connects unstructured Telegram vacancies to a human-reviewed application process. The product combines conservative extraction, evidence-based preference scoring, a CRM with explicit submission confirmation, versioned CV preparation and descriptive application analytics. It runs locally, supports Basic Mode without a paid API and can use an installed Ollama model for constrained evidence selection. The public portfolio demo uses only fictional data. Real Telegram activation requires the owner's official authorization.

**Featured description:** Explore JobFlow AI's fictional workspace and twelve-part product case study: discovery, interpretable matching, factual application preparation and accountable tracking.

**Relevant skills:** Product discovery, MVP scoping, Business Analysis, Requirements engineering, Data modeling, API integration, Python, SQL/SQLite, Product analytics, Human-in-the-loop AI, Privacy by design, Testing, Technical communication.

## Interview: Product Manager story

The problem was coordination across community posts, a CV, application drafts and a tracking sheet. I prioritized a repeatable loop: discover, inspect fit, prepare with evidence, submit manually, track outcomes. Local-first reduced hosting and privacy overhead for a single owner. Basic Mode made the core workflow usable before an AI model or Telegram credentials were available. The next decision should come from actual usage: collect weekly effort logs and relevance labels, then address the most frequent parser or workflow failures.

## Interview: Business Analyst story

I translated the brief into source/message identities, explicit missing fields, hard restrictions versus unknown eligibility, evidence statuses, CV/letter references and application state transitions. A generated letter cannot imply a submitted application. I made this a rule in persistence and an explicit UI confirmation. Extraction errors remain correctable while the original publication is preserved. Tests verify these contracts, including cursor transactions and edit/delete handling.

## Interview: AI Product Manager story

I started with the risk of invented experience. The AI boundary permits selection of approved evidence IDs, rather than free-form candidate claims. The output uses a constrained schema and is independently checked. An installed qwen3:8b model selected a supported SQL fact on a fictional fixture; the first unconstrained probe returned an invalid ID. That observation motivated validation and Basic fallback. It is a narrow technical check, not a benchmark of multilingual drafting quality or recruitment effectiveness.

## Architecture explanation

FastAPI serves a same-origin interface on loopback. SQLite transactions persist each message together with a catch-up cursor. Telethon's live handlers never move that cursor, so an out-of-order event cannot skip earlier messages. Polling resumes oldest-first and reconciles a bounded recent window. Background notifications use a durable outbox. An uncertain send is marked ambiguous instead of being automatically retried. The public Pages build regenerates an explicit fictional seed and copies only allowed static files.

## Privacy and security decisions

The local launch URL has a one-use fragment token that is removed before API login; subsequent requests use an HttpOnly SameSite cookie and CSRF token. Host/Origin checks, escaped content, CSP, upload limits and validated database restoration reduce common local-web risks. Windows restricts the private directory to the current user. The database is not independently encrypted, and downloaded backups remain the owner's responsibility. Multi-user or remote hosting requires a different security design.

## Metrics explanation

Application funnels use recorded events and explicit cohorts; skipped stages are not filled in. Response rate uses manually confirmed Applied applications as its denominator. Precision@10 appears only after the top ten available results are labelled; recall requires the entire bounded collection to be labelled. Source, role and CV comparisons are descriptive and subject to selection and small-sample bias. Weekly effort logs allow before/after observation without claiming causality or improvement before it is measured.

## Roadmap prioritization

1. Personally authorize Telegram and add the real CV privately; verify bounded message coverage and a few complete applications.
2. Label a fixed sample and correct the most common extraction and eligibility errors; monitor source and parser drift.
3. Measure comparable baseline/JobFlow weeks and discovery-to-application intervals.
4. Expand semantic matching or multilingual evidence management only if the measured failure pattern justifies it.
5. Consider multi-user hosting after explicit consent, threat modeling and access-control design; keep submission under human control.
