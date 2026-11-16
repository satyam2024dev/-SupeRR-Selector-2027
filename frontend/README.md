# SupeRR Selector 2027 — frontend foundation

React + TypeScript interface and a separate read-only FastAPI adapter. The Streamlit application remains the working analytics product during this migration phase.

## Start locally (PowerShell)

From `D:\ipl\SUPERR_SELECTOR_2027`:

```powershell
py -3 -m venv api\.venv
api\.venv\Scripts\python.exe -m pip install -r api\requirements.txt
api\.venv\Scripts\python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

The Vite server binds to `127.0.0.1:5173`; the API binds to `127.0.0.1:8000`. The frontend API base defaults to `http://127.0.0.1:8000/api/v1`; copy `.env.example` to `.env.local` only to override that local address. API CORS allows only the two local Vite origins and GET/OPTIONS.

## Read-only API

- `GET /api/v1/health`
- `GET /api/v1/overview`
- `GET /api/v1/rankings/batters/overall`
- `GET /api/v1/rankings/batters/supporting?format=IPL|T20I`
- `GET /api/v1/rankings/batters?format=IPL|T20I&limit=200`
- `GET /api/v1/players?query=&format=&role=&limit=100`
- `GET /api/v1/players/comparison-candidates?format=IPL|T20I&query=&limit=200`
- `GET /api/v1/players/{player_id}/profiles?format=`
- `GET /api/v1/players/compare?ids=...&format=IPL|T20I`
- `GET /api/v1/bowling/evidence`
- `GET /api/v1/auction/availability?role=&status=`
- `GET /api/v1/auction/targets`
- `GET /api/v1/methodology`
- `GET /api/v1/data-quality`

The adapter reads only existing reports and submission artifacts. It does not run analytics pipelines or calculate/reorder scores. Missing artifacts return explicit empty/unavailable states. Bowling evidence preserves the project's 0 competition-ready / 414 exploratory distinction.

## Validation commands

```powershell
cd frontend
npm.cmd test
npm.cmd run build
npm.cmd run capture:screenshots
cd ..
api\.venv\Scripts\python.exe -m pytest -q api\tests
```

Screenshot capture uses the installed Microsoft Edge browser and Playwright Core to render all seven application sections at 1440 x 1200 desktop, 1024 x 1000 laptop, 768 x 1024 tablet, and 390 x 844 mobile CSS viewports. It writes captures to `frontend/screenshots/` and fails on horizontal overflow.

Run existing project analytics tests with the project's established environment and commands; this frontend does not update those dependencies.

## Auction overlay packaging

`data/external/ipl_2027_player_availability.csv` is an ignored, separately maintained local overlay. The approved decision is to keep it local and operator-managed. This application reads it if present and never generates a replacement. Do not add it to Git, remove its ignore rule, or infer missing statuses. Until official registration/final-register records are added, registered auction targets remain zero and availability remains provisional.

For a safe operator update, preserve a local backup first, then update the overlay only from player-specific official announcements. Record each source URL, publication date, verification date, status, confidence and explanation. Verify the schema, player IDs, dates, duplicate IDs/roles and the official-registration gate before using the refreshed file. The module `python -m src.ipl_2027_availability` rebuilds and overwrites the overlay; run it only when deliberately refreshing from the curated official transaction records. Keep the file local and verify it remains ignored with `git check-ignore -v data/external/ipl_2027_player_availability.csv` in a Git checkout. If the overlay is absent, retain the explicit API unavailable state; never substitute predicted status. The approved decision and scope are recorded in `docs/auction_overlay_distribution_options.md`.

## Phase 4 scouting pages

- Player Comparison uses the read-only `/players` and `/players/compare` endpoints. Same-format Phase 5C score and stored descriptive profile values are displayed as served; the UI does not calculate rankings.
- Bowling Intelligence uses `/bowling/evidence` and the Phase 5H audit artifacts. It preserves the 0 competition-ready / 414 exploratory status and documents source-semantic gaps.
- RR Auction Targets uses `/rankings/batters/overall`, `/auction/targets`, `/auction/availability`, and `/bowling/evidence`. The performance Top 10 and availability-qualified list remain independent. The final auction register is not available in the current snapshot.
- The API test client uses HTTPX ASGI transport directly instead of Starlette `TestClient`, avoiding its deprecated httpx integration without upgrading existing Python dependencies.
