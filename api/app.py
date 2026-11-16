"""Read-only local API for the SupeRR Selector React foundation."""
from __future__ import annotations

import csv
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs" / "reports"
SUBMISSION = ROOT / "submission"
EXTERNAL = ROOT / "data" / "external"
API_VERSION = "1.0.0"

app = FastAPI(
    title="SupeRR Selector Local API",
    version=API_VERSION,
    description="Read-only adapter over existing validated SupeRR Selector artifacts.",
    docs_url="/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)

IDENTIFIER_FIELDS = {"player_id", "match_id", "team_id", "comp_id", "venue_id"}
BOOLEAN_FIELDS = {
    "competition_ready", "performance_eligible", "descriptive_profile_usable",
    "sufficient_evidence_for_future_pressure_comparison", "meets_existing_floors",
    "meets_competition_floor", "baseline_evidence_eligible",
    "verified_pressure_evidence_eligible", "proxy_exploration_eligible",
}


def _scalar(field: str, value: str | None) -> Any:
    if value is None or value == "":
        return None
    if field in IDENTIFIER_FIELDS:
        return str(value)
    if field.endswith("_json"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    lowered = value.casefold()
    if field in BOOLEAN_FIELDS or field.startswith("is_") or field.endswith("_known"):
        if lowered in {"true", "1"}:
            return True
        if lowered in {"false", "0"}:
            return False
    if lowered in {"nan", "inf", "+inf", "-inf"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except ValueError:
        return value


@lru_cache(maxsize=64)
def _read_csv_cached(path_text: str, modified_ns: int, size: int) -> tuple[dict[str, Any], ...]:
    path = Path(path_text)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return tuple(
            {key: _scalar(key, value) for key, value in row.items()}
            for row in csv.DictReader(stream)
        )


def _rows(directory: Path, filename: str, *, required: bool = True) -> list[dict[str, Any]]:
    # Callers pass only source-code constants; client-supplied paths are never accepted.
    path = directory / filename
    if not path.is_file():
        if required:
            raise HTTPException(status_code=503, detail=f"Required artifact unavailable: {filename}")
        return []
    stat = path.stat()
    return [dict(row) for row in _read_csv_cached(str(path), stat.st_mtime_ns, stat.st_size)]


def _markdown(directory: Path, filename: str) -> str:
    path = directory / filename
    if not path.is_file():
        raise HTTPException(status_code=503, detail=f"Required artifact unavailable: {filename}")
    return path.read_text(encoding="utf-8-sig")


def _by_rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # This sorts by the stored rank field only; it never calculates a score or rank.
    return sorted(rows, key=lambda row: row.get("rank") if row.get("rank") is not None else 10**9)


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    checks = {
        "overall_batter_top10": (SUBMISSION / "phase5g_overall_batter_top10.csv").is_file(),
        "phase5c_batter_rankings": (REPORTS / "phase5c_batter_rankings.csv").is_file(),
        "phase5c_bowler_rankings": (REPORTS / "phase5c_bowler_rankings.csv").is_file(),
        "auction_availability_overlay": (EXTERNAL / "ipl_2027_player_availability.csv").is_file(),
    }
    return {"status": "ok", "api_version": API_VERSION, "artifacts": checks}


@app.get("/api/v1/overview")
def overview() -> dict[str, Any]:
    coverage = _rows(REPORTS, "confirmed_scope_coverage_summary.csv")
    batters = _rows(REPORTS, "phase5c_batter_rankings.csv")
    bowlers = _rows(REPORTS, "phase5c_bowler_rankings.csv")
    top10 = _rows(SUBMISSION, "phase5g_overall_batter_top10.csv")
    formats = [
        {
            "format": row.get("format"),
            "matches": row.get("match_count"),
            "deliveries": row.get("delivery_count"),
            "seasons": row.get("season_labels"),
        }
        for row in coverage
    ]
    return {
        "source": "outputs/reports/confirmed_scope_coverage_summary.csv",
        "overall_top10_source": "submission/phase5g_overall_batter_top10.csv",
        "formats": formats,
        "matches_analyzed": sum(int(row.get("match_count") or 0) for row in coverage),
        "deliveries_analyzed": sum(int(row.get("delivery_count") or 0) for row in coverage),
        "eligible_batter_player_format_rows": sum(
            row.get("format") in {"IPL", "T20I"} and row.get("competition_ready") is True
            for row in batters
        ),
        "eligible_batter_distinct_players": len({
            str(row.get("player_id")) for row in batters
            if row.get("format") in {"IPL", "T20I"}
            and row.get("competition_ready") is True
            and row.get("player_id") is not None
        }),
        "overall_batter_top10_count": len(top10),
        "bowling": {
            "source": "outputs/reports/phase5c_bowler_rankings.csv",
            "competition_ready": sum(row.get("competition_ready") is True for row in bowlers),
            "exploratory": sum(row.get("competition_ready") is not True for row in bowlers),
        },
        "availability_snapshot": max(
            (row.get("verification_date") for row in (_availability() or []) if row.get("verification_date")),
            default=None,
        ),
    }


@app.get("/api/v1/rankings/batters/overall")
def overall_batter_ranking() -> dict[str, Any]:
    records = _rows(SUBMISSION, "phase5g_overall_batter_top10.csv")
    return {
        "source": "submission/phase5g_overall_batter_top10.csv",
        "methodology": "Phase 5G mean within-format percentile; authoritative stored order.",
        "count": len(records),
        "records": records,
    }


@app.get("/api/v1/rankings/batters/supporting")
def supporting_batter_rankings(format: str = Query(pattern="^(IPL|T20I)$")) -> dict[str, Any]:
    filename = f"supporting_{format}_batter_top10.csv"
    records = _by_rank(_rows(SUBMISSION, filename))
    return {"source": f"submission/{filename}", "format": format, "count": len(records), "records": records}


@app.get("/api/v1/rankings/batters")
def format_batter_rankings(
    format: str = Query(pattern="^(IPL|T20I)$"),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    records = _rows(REPORTS, "phase5c_batter_rankings.csv")
    selected = [
        row for row in records
        if row.get("format") == format and row.get("competition_ready") is True
    ]
    selected = _by_rank(selected)[:limit]
    return {
        "source": "outputs/reports/phase5c_batter_rankings.csv",
        "format": format,
        "count": len(selected),
        "eligible_only": True,
        "records": selected,
    }


@app.get("/api/v1/players")
def players(
    query: str = Query(default="", max_length=100),
    format: str | None = Query(default=None, pattern="^(IPL|T20I)$"),
    role: str | None = Query(default=None, pattern="^(batter|bowler)$"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    records = _rows(REPORTS, "player_exposure_summary.csv")
    needle = query.strip().casefold()
    if needle:
        records = [row for row in records if needle in str(row.get("player_name") or "").casefold()
                   or needle in str(row.get("player_id") or "").casefold()]
    if format:
        records = [row for row in records if row.get("format") == format]
    if role:
        records = [row for row in records if row.get("role") == role]
    records.sort(key=lambda row: (str(row.get("player_name") or "").casefold(), str(row.get("format") or "")))
    return {"source": "outputs/reports/player_exposure_summary.csv", "count": len(records[:limit]), "records": records[:limit]}


@app.get("/api/v1/players/comparison-candidates")
def comparison_candidates(
    format: str = Query(pattern="^(IPL|T20I)$"),
    query: str = Query(default="", max_length=100),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    """Return eligible batters from stored Phase 5C rankings with any matching exposure rows."""
    rankings = [
        row for row in _rows(REPORTS, "phase5c_batter_rankings.csv")
        if row.get("format") == format and row.get("competition_ready") is True
    ]
    exposures = [row for row in _rows(REPORTS, "player_exposure_summary.csv") if row.get("format") == format and row.get("role") == "batter"]
    exposure_by_id = {str(row.get("player_id")): row for row in exposures}
    needle = query.strip().casefold()
    rankings = _by_rank(rankings)
    records = []
    for ranking in rankings:
        player_id = str(ranking.get("player_id"))
        name = str(ranking.get("player_name") or "")
        if needle and needle not in name.casefold() and needle not in player_id.casefold():
            continue
        records.append({
            **exposure_by_id.get(player_id, {}),
            "player_id": player_id,
            "player_name": name,
            "role": "batter",
            "format": format,
            "performance_eligible": True,
            "ranking_evidence": ranking,
        })
        if len(records) >= limit:
            break
    return {"source": "outputs/reports/phase5c_batter_rankings.csv and outputs/reports/player_exposure_summary.csv", "format": format, "eligible_only": True, "count": len(records), "records": records}


@app.get("/api/v1/players/{player_id}/profiles")
def player_profiles(player_id: str, format: str | None = Query(default=None, pattern="^(IPL|T20I)$")) -> dict[str, Any]:
    exposure = [row for row in _rows(REPORTS, "player_exposure_summary.csv") if str(row.get("player_id")) == player_id]
    if format:
        exposure = [row for row in exposure if row.get("format") == format]
    profiles: dict[str, list[dict[str, Any]]] = {}
    for role, filename in (("batter", "batter_performance_profile.csv"), ("bowler", "bowler_performance_profile.csv")):
        matches = [row for row in _rows(REPORTS, filename) if str(row.get("player_id")) == player_id]
        if format:
            matches = [row for row in matches if row.get("format") == format]
        profiles[role] = matches
    overall = [row for row in _rows(SUBMISSION, "phase5g_overall_batter_top10.csv") if str(row.get("player_id")) == player_id]
    supporting = [
        row for row in _rows(REPORTS, "phase5c_batter_rankings.csv")
        if str(row.get("player_id")) == player_id and (format is None or row.get("format") == format)
    ]
    if not exposure and not overall and not supporting:
        raise HTTPException(status_code=404, detail="No supported player evidence found for this ID")
    return {
        "player_id": player_id,
        "player_name": (exposure or overall or supporting)[0].get("player_name"),
        "source": "Phase 5G overall ranking, Phase 5C format ranking, exposure, and descriptive profile artifacts",
        "exposure": exposure,
        "profiles": profiles,
        "ranking_evidence": {"overall": overall, "formats": supporting},
    }


@app.get("/api/v1/players/compare")
def compare_players(
    ids: str = Query(min_length=1, max_length=100),
    format: str | None = Query(default=None, pattern="^(IPL|T20I)$"),
) -> dict[str, Any]:
    requested = [value.strip() for value in ids.split(",") if value.strip()]
    if not 2 <= len(requested) <= 4 or len(set(requested)) != len(requested):
        raise HTTPException(status_code=422, detail="Provide two to four distinct player IDs")
    exposure_rows = _rows(REPORTS, "player_exposure_summary.csv")
    batters = _rows(REPORTS, "batter_performance_profile.csv")
    bowlers = _rows(REPORTS, "bowler_performance_profile.csv")
    rankings = _rows(REPORTS, "phase5c_batter_rankings.csv")
    result = []
    for player_id in requested:
        exposure = [row for row in exposure_rows if str(row.get("player_id")) == player_id and (format is None or row.get("format") == format)]
        profiles: dict[str, list[dict[str, Any]]] = {}
        for role, rows in (("batter", batters), ("bowler", bowlers)):
            profiles[role] = [row for row in rows if str(row.get("player_id")) == player_id and (format is None or row.get("format") == format)]
        ranking_evidence = [
            row for row in rankings
            if str(row.get("player_id")) == player_id
            and row.get("competition_ready") is True
            and (format is None or row.get("format") == format)
        ]
        if not exposure and not ranking_evidence and not profiles["batter"] and not profiles["bowler"]:
            raise HTTPException(status_code=404, detail=f"No supported profile or ranking evidence found for player ID {player_id}")
        name = (exposure or ranking_evidence or profiles["batter"] or profiles["bowler"])[0].get("player_name")
        result.append({"player_id": player_id, "player_name": name, "exposure": exposure, "profiles": profiles, "ranking_evidence": ranking_evidence})
    return {"source": "existing player exposure and descriptive profile artifacts", "format": format, "count": len(result), "records": result}

@app.get("/api/v1/bowling/evidence")
def bowling_evidence() -> dict[str, Any]:
    profiles = _rows(REPORTS, "phase5c_bowler_rankings.csv")
    metric_audit = _rows(SUBMISSION, "phase5h_bowling_metric_audit.csv")
    eligibility = _rows(SUBMISSION, "phase5h_bowling_eligibility.csv")
    return {
        "competition_ready": sum(row.get("competition_ready") is True for row in profiles),
        "exploratory_profiles": sum(row.get("competition_ready") is not True for row in profiles),
        "ranked_recommendations_supported": False,
        "metric_audit_source": "submission/phase5h_bowling_metric_audit.csv",
        "metric_audit": metric_audit,
        "eligibility_source": "submission/phase5h_bowling_eligibility.csv",
        "eligibility": eligibility,
        "limitations_source": "submission/phase5h_bowling_final_audit.md",
        "limitations_report": _markdown(SUBMISSION, "phase5h_bowling_final_audit.md"),
    }


def _availability() -> list[dict[str, Any]] | None:
    path = EXTERNAL / "ipl_2027_player_availability.csv"
    if not path.is_file():
        return None
    return _rows(EXTERNAL, "ipl_2027_player_availability.csv", required=False)


@app.get("/api/v1/auction/availability")
def auction_availability(
    role: str | None = Query(default=None, pattern="^(batter|bowler)$"),
    status: str | None = Query(default=None, max_length=64),
) -> dict[str, Any]:
    records = _availability()
    if records is None:
        return {
            "overlay_present": False,
            "as_of": None,
            "count": 0,
            "records": [],
            "reason": "The Git-ignored availability overlay is not present in this environment; no substitute data was generated.",
        }
    if role:
        records = [row for row in records if row.get("candidate_role") == role]
    if status:
        records = [row for row in records if row.get("ipl_2027_status") == status]
    dates = [row.get("verification_date") for row in records if row.get("verification_date")]
    return {
        "overlay_present": True,
        "source": "data/external/ipl_2027_player_availability.csv",
        "as_of": max(dates) if dates else None,
        "count": len(records),
        "records": records,
    }


@app.get("/api/v1/auction/targets")
def auction_targets() -> dict[str, Any]:
    records = _availability()
    if records is None:
        return {"overlay_present": False, "as_of": None, "count": 0, "targets": [], "reason": "Availability overlay is not present."}
    eligible = [
        row for row in records
        if row.get("candidate_role") == "batter"
        and row.get("performance_eligible") is True
        and row.get("ipl_2027_status") in {"officially_registered_for_auction", "included_in_final_auction_register"}
    ]
    eligible.sort(key=lambda row: row.get("performance_rank_ipl") if row.get("performance_rank_ipl") is not None else 10**9)
    dates = [row.get("verification_date") for row in records if row.get("verification_date")]
    return {
        "overlay_present": True,
        "source": "data/external/ipl_2027_player_availability.csv",
        "as_of": max(dates) if dates else None,
        "count": len(eligible),
        "targets": eligible,
        "empty_reason": "No performance-qualified batter has a verified auction-pool status in this snapshot." if not eligible else None,
    }


@app.get("/api/v1/methodology")
def methodology() -> dict[str, Any]:
    return {
        "source": "submission/phase5h_methodology_report.md",
        "bowling_limitations_source": "submission/phase5h_bowling_final_audit.md",
        "report": _markdown(SUBMISSION, "phase5h_methodology_report.md"),
        "bowling_limitations": _markdown(SUBMISSION, "phase5h_bowling_final_audit.md"),
    }


@app.get("/api/v1/data-quality")
def data_quality() -> dict[str, Any]:
    return {
        "scope_source": "outputs/reports/confirmed_scope_coverage_summary.csv",
        "inventory_source": "outputs/reports/dataset_inventory.csv",
        "quality_source": "outputs/reports/data_quality_report.csv",
        "scope": _rows(REPORTS, "confirmed_scope_coverage_summary.csv"),
        "inventory": _rows(REPORTS, "dataset_inventory.csv"),
        "quality": _rows(REPORTS, "data_quality_report.csv"),
    }
