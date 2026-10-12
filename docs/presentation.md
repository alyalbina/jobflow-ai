# Portfolio presentation

The case frames JobFlow as a product decision system: from scattered opportunities to a clear next step. The cover and six-step artwork describe the workflow; the workspace image is an actual published browser capture from the earlier interface verification.

## Visual direction

Warm paper `#f3f2eb`, forest ink `#173e33`, muted green `#5c7065` and chartreuse `#d4ec88`. Manrope is hosted locally with Latin and Cyrillic subsets and its SIL Open Font License. Large, quiet typography introduces the problem; thin rules and numbered chapters organize the detailed evidence. A single filled action opens the fictional sandbox.

## Presentation assets

- `web/assets/portfolio/cover.svg`: editable vector cover.
- `web/assets/portfolio/cover.png`: README cover, 1600 × 900.
- `web/assets/portfolio/social-preview.png`: social card, 1280 × 640.
- `web/assets/portfolio/workspace.jpg`: unmodified published-demo capture, reused from `docs/screenshots/published-demo.jpg`.
- `web/case-study.html` and `web/case-study.ru.html`: English and Russian portfolio stories.

The presentation distinguishes product requirements, AI-assisted implementation, executed checks and future validation. It does not introduce new hiring outcomes or claim live Telegram verification. Existing architecture, metrics, setup and security documentation remain the detailed references.

## Verification on 13 October 2026

The public package builds with an explicit allowlist, the public-boundary scan passes, and all 56 existing automated tests pass. Ruff lint and formatting checks pass. Local integrity inspection finds no missing case-page assets or section anchors. Public browser checks and screenshots are recorded separately after deployment.

## Published browser review on 13 October 2026

Both language versions loaded in the public Pages deployment. The published screenshot asset loaded, the local Manrope typography rendered, and the desktop document had no horizontal overflow at a 1348 CSS-pixel viewport. Language links and section navigation were exercised. These checks cover the case presentation, not a new cross-device certification of the underlying app.

[English case capture](screenshots/redesigned-case-en.jpg) · [Russian case capture](screenshots/redesigned-case-ru.jpg). The captures are unmodified browser screenshots. README covers and GitHub social previews are separately authored presentation graphics.
