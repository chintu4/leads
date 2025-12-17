# Copilot / AI agent instructions — Leads project (backend + frontend)

## Purpose
Provide concise, repository-specific guidance for AI coding agents so they can be productive immediately. Focus on how the system is structured, where to make changes, how to run tests and deployments, and key conventions.

## Big-picture architecture
- Two main components:
  - backend/ (FastAPI) — Scrapes search results, runs crawlers (Scrapy + Playwright), processes/enriches leads, streams progress via SSE. Key entrypoints: `main.py` (API), `src/handlers/handle.py` (scrape/process flows).
  - frontend/ (React + TypeScript) — UI displays streaming progress, results table, and triggers `/process` and export endpoints. Key file: `src/LeadFinder.tsx` and `components/ResultsTable.tsx`.
- Data flow: query -> DuckDuckGo search (`src/utils/duck.py`) -> initial search results -> optional Scrapy crawl (`src/utils/scrapy_ok.py`) -> optional deep Playwright crawl (`src/utils/playwright_deep.py`) -> `process()` in `handle.py` -> SSE / REST responses to frontend.

## Key files & responsibilities (quick map)
- backend/main.py — FastAPI app, SSE `/scrape/stream`, `/scrape` and `/process` endpoints
- backend/src/handlers/handle.py — Core orchestration (duck, crawl, deep crawl, process, progress events)
- backend/src/utils/duck.py — Search integration (DDG)
- backend/src/utils/scrapy_ok.py — Spider for one-off page extraction
- backend/src/utils/playwright_deep.py — In-depth site crawling for people (Playwright)
- backend/src/utils/profile.py — Heuristics for `is_profile_url(url, page_text, jsonld_texts)` (used heavily for filtering)
- backend/src/utils/* — contact extraction, logging, settings
- frontend/src/LeadFinder.tsx — SSE client, UI state, error handling
- frontend/src/components/ResultsTable.tsx — Display rows, profile link logic

## Project-specific conventions & patterns
- SSE events use dict shapes: {type: 'progress'|'search_results'|'item'|'error'|'done', ...}. See `handle.scrape_progress` for shapes and ordering.
- Profile-first approach: server prioritizes/filters profile-like URLs (LinkedIn `/in/`, ResearchGate, ORCID, Google Scholar). Heuristic logic lives in `src/utils/profile.py` and is enforced server-side in `handle.py`.
- Playwright usage is defensive/lazy to avoid import-time failure; env flags control deep crawling (`USE_PLAYWRIGHT_DEEP`, `ALLOW_LINKEDIN_DEEP`).
- Timeouts & retries: `CRAWL_TIMEOUT`, `DEEP_TIMEOUT_S`, `DEEP_MAX_PAGES` are configured via env vars. Playwright navigation timeout set in `CrawlConfig`.

## Developer workflows & commands
- Tests: run `pytest -q` from repo root (backend and frontend tests live under `backend/tests/`).
- Run backend locally: `python -m main` (or `py main.py`) starts uvicorn as implemented in `main.py`.
- Run frontend in dev: use `bun`/`npm`/`pnpm` per `frontend/package.json`. Frontend dev server runs on port 3000 and expects backend on port 8000.
- Playwright setup: `python -m playwright install chromium` and ensure `playwright` package is installed.
- Quick targeted deep crawl (diagnostics): `py backend/scripts/run_pubmed_deep.py` (prints progress and diagnostics via a callback).

## Testing & debugging tips
- Backend logs are written to `backend/logs/backend.log` — search for `sse: enqueue event`, `Deep Playwright crawl failed`, and `Crawl timed out` messages.
- If SSE shows an error in frontend, check logs for the 'msg' and 'url' fields (backend includes URL/phase context in error messages).
- Unit tests include `backend/tests/test_profile_filtering.py` (server-side profile filtering) and SSE tests `test_sse.py` to validate streaming behavior.

## How to approach common tasks (examples)
- Add a new profile host (e.g., `orcid.org`): update `src/utils/profile.py` tokens and add tests to ensure `is_profile_url` returns (True, score) and that `handle.scrape_progress` emits only profile-like `search_results` and `item` events.
- Debugging a deep crawl timeout for a specific URL:
  1. Run `py backend/scripts/run_pubmed_deep.py` (adjust timeouts via env vars or `CrawlConfig` in the script).
  2. Inspect `backend/logs/backend.log` for `navigation timeout` or `Crawl timed out` warnings.
  3. Re-run with `DEEP_TIMEOUT_S=300` if the site is slow, or add diagnostic logging/HTML snapshot on failure inside `playwright_deep.py`.

## Security & external integrations
- Google Sheets export uses `src/handlers/google_export.py` and requires OAuth flow in `src/handlers/auth_google.py` — check `main.py` for `/auth/google` and `/auth/session` routes.
- Avoid crawling sites that block automation; Playwright does not bypass logins and LinkedIn crawling is disabled by default unless `ALLOW_LINKEDIN_DEEP=1`.

## Quick checklist for AI edits
- Prefer small, test-backed changes. Add unit tests under `backend/tests/` and use the SSE test patterns as examples.
- Preserve server-side profile filtering (it is expected by the frontend and tests).
- When modifying Playwright code, ensure proper lazy import and defensive error handling (playwright may not be available on CI/dev machines).

---

If you'd like, I can expand this with a Playwright troubleshooting runbook or add a small "how to add a crawler" recipe. Any parts you'd like clarified or expanded? 
o Grant Expiry: Finding grants that just started vs. 
those ending. 