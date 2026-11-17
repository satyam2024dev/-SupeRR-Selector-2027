# SupeRR Selector Season 2

**Cricket Talent Intelligence Platform**


link of the website : https://supe-rr-selector-2027-delta.vercel.app/


An evidence-led scouting and analytics application for IPL and T20I data. The Streamlit dashboard presents validated batter rankings, descriptive player profiles, match and pressure analysis, bowling evidence limits, and the current submission package.

## Architecture

- `data/raw/`: local, original source files; do not commit or upload them.
- `data/processed/`, `data/external/`: governed derived/reference data.
- `src/`: data loading, validation, cricket metrics, eligibility, scoring, comparison, and audit pipelines.
- `dashboard/`: Streamlit application and shared interface components.
- `notebooks/`: staged analysis notebooks.
- `tests/`: software tests using synthetic fixtures.
- `outputs/`: generated charts and reports.
- `submission/`: preserved final submission package and its supporting evidence.

## Run the dashboard

From the project root:

```powershell
.\venv\Scripts\streamlit.exe run dashboard/app.py
```

The application reads local source data and validated artifacts using paths relative to the project root. It does not modify raw datasets or recalculate rankings in the dashboard.

## Tests

```powershell
.\venv\Scripts\python.exe -m pytest -q tests
```

Synthetic fixtures in tests are not competition players or statistics. See `submission/README.md` and the Phase 5H reports for the current ranking and bowling readiness decisions.

## Privacy

Keep original proprietary data in `data/raw/`; do not send it to external services or public repositories. Check staged files before every commit.

## IPL 2027 availability overlay

`data/external/ipl_2027_player_availability.csv` is a separate, auditable overlay over IPL Phase 5C batter and bowler profiles. It does not change raw data, the validated Phase 5G overall Batter Top 10, or ranking calculations. Availability records carry a verification date and source references. Last observed franchise is sourced from the 2026 project mapping and is not treated as a 2027 contract.

Refresh the profile overlay after verifying new official IPL/BCCI/franchise announcements:

```powershell
.\venv\Scripts\python.exe -m src.ipl_2027_availability
```

Update `VERIFIED_TRANSACTIONS` in `src/ipl_2027_availability.py` only from official announcements, with the player's local ID, source URL, publication date, and transfer details. Retention/release and auction-registration statuses must be updated from official lists; release alone does not qualify a player for the auction target shortlist. As checked on 13 November 2026, the 2027 retention deadline, registration close, and final register were still pending. The dashboard therefore shows no confirmed batter targets. Bowling availability remains separate from the 0 competition-ready / 414 exploratory evidence decision.
